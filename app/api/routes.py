from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.domain import (
    ActivityLog,
    Campaign,
    CampaignAssignment,
    CapacityLedger,
    Client,
    ClientContact,
    Deal,
    DealAttachment,
    DealProductLine,
    DealStatus,
    Deliverable,
    DeliverableType,
    DeliverableStage,
    DeliverableStatus,
    GlobalHealth,
    GlobalStatus,
    BenchmarkTarget,
    Escalation,
    ManualRisk,
    Milestone,
    PerformanceResult,
    Publication,
    ProductModule,
    Comment,
    ReviewRoundEvent,
    ReviewWindow,
    ReviewWindowStatus,
    ReviewWindowType,
    RiskSeverity,
    Review,
    Note,
    SowChangeApproval,
    SowChangeRequest,
    Role,
    RoleName,
    TeamName,
    SeniorityLevel,
    AppAccessRole,
    Stage,
    SystemRisk,
    User,
    UserRoleAssignment,
    WorkflowStep,
    WorkflowStepEffort,
    WorkflowStepDependency,
)
from app.schemas.campaigns import CampaignAssignmentsUpdateIn, CampaignDatesUpdateIn, CampaignOut, CampaignStatusUpdateIn
from app.schemas.admin import (
    AdminUserCreateIn,
    AdminUserRolesUpdateIn,
    OpsDefaultsUpdateIn,
    RolePermissionsUpdateIn,
)
from app.schemas.deals import DealCreateIn, DealOut, OpsApproveIn, SowChangeApproveIn, SowChangeCreateIn
from app.schemas.deliverables import (
    CapacityOverrideDecisionIn,
    CapacityOverrideRequestIn,
    DeliverableDatesUpdateIn,
    DeliverableDueUpdateIn,
    DeliverableOwnerUpdateIn,
    DeliverableStageUpdateIn,
    DeliverableTransitionIn,
    ReviewRoundIncrementIn,
)
from app.schemas.risks import EscalationResolveIn, ManualRiskCreateIn, ManualRiskUpdateIn
from app.schemas.workflow import StepCompleteIn, StepManageIn, StepOverrideDueIn
from app.services.authz_service import AuthzService
from app.services.campaign_generation_service import CampaignGenerationService
from app.services.capacity_override_service import CapacityOverrideService
from app.services.capacity_service import CapacityService
from app.services.change_control_service import ChangeControlService
from app.services.deliverable_workflow_service import DeliverableWorkflowService
from app.services.deal_service import DealService
from app.services.ops_job_service import OpsJobService
from app.services.workflow_engine_service import WorkflowEngineService
from app.services.id_service import PublicIdService
from app.services.my_work_queue_service import MyWorkQueueService
from app.services.calendar_service import build_default_working_calendar
from app.services.ops_defaults_service import OpsDefaultsService
from app.services.campaign_health_service import CampaignHealthService
from app.services.timeline_health_service import TimelineHealthService
from app.services.stage_integrity_service import StageIntegrityService


router = APIRouter(prefix="/api", tags=["campaign-ops"])

TModel = TypeVar("TModel")

APP_CONTROL_IDS: set[str] = {
    "run_ops_job",
    "refresh_data",
    "admin_add_user",
    "admin_edit_user_name",
    "admin_edit_user_email",
    "admin_set_user_team",
    "admin_set_user_seniority_manager",
    "admin_set_user_seniority_leadership",
    "admin_set_user_app_role_admin",
    "admin_set_user_app_role_superadmin",
    "admin_remove_user",
}


def _is_app_control(control_id: str) -> bool:
    return str(control_id).startswith("admin_") or control_id in APP_CONTROL_IDS


def _actor_has_full_scope_campaign_visibility(actor: Any) -> bool:
    return (
        actor.app_role in {AppAccessRole.ADMIN, AppAccessRole.SUPERADMIN}
        or actor.seniority == SeniorityLevel.LEADERSHIP
    )


def _resolve_by_identifier(db: Session, model: type[TModel], identifier: str) -> TModel | None:
    # Compatibility: allow both internal UUID and display ID during transition.
    by_pk = db.get(model, identifier)
    if by_pk:
        return by_pk
    return db.scalar(select(model).where(model.display_id == identifier))


def _campaign_for_deliverable(db: Session, deliverable: Deliverable) -> Campaign | None:
    if deliverable.campaign_id:
        campaign = db.get(Campaign, deliverable.campaign_id)
        if campaign:
            return campaign
    return None


def _step_linked_deliverable(step: WorkflowStep) -> str | None:
    return step.linked_deliverable_id


def _coerce_campaign_status(status: str | None) -> str:
    return _normalize_campaign_status(status).value


def _evaluate_deliverable_health(db: Session, deliverable: Deliverable) -> dict[str, Any]:
    campaign = db.get(Campaign, deliverable.campaign_id) if deliverable.campaign_id else None
    steps = db.scalars(
        select(WorkflowStep).where(
            WorkflowStep.linked_deliverable_id == deliverable.id
        )
    ).all()
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if steps:
        step_ids = [s.id for s in steps]
        for effort in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
    evaluation = TimelineHealthService(db).evaluate_deliverable(
        deliverable=deliverable,
        campaign=campaign,
        steps=steps,
        efforts_by_step_id=efforts_by_step,
    )
    return {
        "health": evaluation.health,
        "health_reason": evaluation.health_reason,
        "buffer_working_days_remaining": evaluation.buffer_working_days_remaining,
        "is_not_due": evaluation.is_not_due,
    }


def _evaluate_deliverable_health_batch(db: Session, deliverables: list[Deliverable]) -> dict[str, dict[str, Any]]:
    if not deliverables:
        return {}

    deliverable_ids = [d.id for d in deliverables]
    campaign_ids = sorted({d.campaign_id for d in deliverables if d.campaign_id})
    campaigns_by_id = (
        {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()}
        if campaign_ids
        else {}
    )

    step_rows = db.scalars(
        select(WorkflowStep).where(
            WorkflowStep.linked_deliverable_id.in_(deliverable_ids)
        )
    ).all()
    steps_by_deliverable: dict[str, list[WorkflowStep]] = {}
    for step in step_rows:
        linked = _step_linked_deliverable(step)
        if linked:
            steps_by_deliverable.setdefault(linked, []).append(step)

    step_ids = [s.id for s in step_rows]
    effort_rows = (
        db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
        if step_ids
        else []
    )
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    for effort in effort_rows:
        efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)

    timeline_health = TimelineHealthService(db)
    payload_by_identifier: dict[str, dict[str, Any]] = {}
    for deliverable in deliverables:
        campaign = campaigns_by_id.get(deliverable.campaign_id) if deliverable.campaign_id else None
        evaluation = timeline_health.evaluate_deliverable(
            deliverable=deliverable,
            campaign=campaign,
            steps=steps_by_deliverable.get(deliverable.id, []),
            efforts_by_step_id=efforts_by_step,
        )
        payload = {
            "health": evaluation.health,
            "health_reason": evaluation.health_reason,
            "buffer_working_days_remaining": evaluation.buffer_working_days_remaining,
            "is_not_due": evaluation.is_not_due,
        }
        payload_by_identifier[deliverable.id] = payload
        payload_by_identifier[deliverable.display_id] = payload
    return payload_by_identifier


def _role_permissions_payload(db: Session) -> dict:
    defaults = OpsDefaultsService(db).get()
    role_permissions = defaults.get("role_permissions") or {}
    return {
        "role_flags": role_permissions.get("role_flags") or {},
        "control_permissions": role_permissions.get("control_permissions") or {},
    }


def _identity_permissions_payload(db: Session) -> dict:
    defaults = OpsDefaultsService(db).get()
    identity_permissions = defaults.get("identity_permissions") or {}
    legacy_controls = identity_permissions.get("control_permissions") or {}
    campaign_controls = identity_permissions.get("campaign_control_permissions") or {}
    app_controls = identity_permissions.get("app_control_permissions") or {}
    return {
        "screen_flags": identity_permissions.get("screen_flags") or {},
        "control_permissions": legacy_controls,
        "campaign_control_permissions": campaign_controls,
        "app_control_permissions": app_controls,
    }


def _identity_rule_allows(rule: dict | None, *, team: TeamName, seniority: SeniorityLevel, app_role: AppAccessRole) -> bool:
    if app_role == AppAccessRole.SUPERADMIN:
        return True
    if not isinstance(rule, dict):
        return False
    teams = {str(v) for v in (rule.get("teams") or [])}
    seniorities = {str(v) for v in (rule.get("seniorities") or [])}
    app_roles = {str(v) for v in (rule.get("app_roles") or [])}
    return (team.value in teams) and (seniority.value in seniorities) and (app_role.value in app_roles)


def _identity_campaign_rule_allows(rule: dict | None, *, team: TeamName, seniority: SeniorityLevel, app_role: AppAccessRole) -> bool:
    if app_role == AppAccessRole.SUPERADMIN:
        return True
    if not isinstance(rule, dict):
        return False
    teams = {str(v) for v in (rule.get("teams") or [])}
    seniorities = {str(v) for v in (rule.get("seniorities") or [])}
    return (team.value in teams) and (seniority.value in seniorities)


def _identity_app_rule_allows(rule: dict | None, *, seniority: SeniorityLevel, app_role: AppAccessRole) -> bool:
    if app_role == AppAccessRole.SUPERADMIN:
        return True
    if not isinstance(rule, dict):
        return False
    seniorities = {str(v) for v in (rule.get("seniorities") or [])}
    app_roles = {str(v) for v in (rule.get("app_roles") or [])}
    return (seniority.value in seniorities) and (app_role.value in app_roles)


def _initials_for_name(name: str | None) -> str:
    parts = [p for p in str(name or "").strip().split() if p]
    if not parts:
        return "--"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _initials_for_user_id(user_id: str | None, users_by_id: dict[str, User]) -> str:
    if not user_id:
        return "--"
    user = users_by_id.get(user_id)
    return _initials_for_name(user.full_name if user else None)


def _legacy_roles_for_identity(primary_team: TeamName, seniority: SeniorityLevel, app_role: AppAccessRole) -> set[RoleName]:
    roles: set[RoleName] = set()
    if app_role in {AppAccessRole.ADMIN, AppAccessRole.SUPERADMIN}:
        roles.add(RoleName.ADMIN)
    if primary_team == TeamName.SALES:
        roles.add(RoleName.AM)
        if seniority in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
            roles.add(RoleName.HEAD_SALES)
    elif primary_team == TeamName.EDITORIAL:
        roles.add(RoleName.CC)
    elif primary_team == TeamName.MARKETING:
        roles.update({RoleName.DN, RoleName.MM})
    elif primary_team == TeamName.CLIENT_SERVICES:
        roles.add(RoleName.CM)
        if seniority in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
            roles.add(RoleName.HEAD_OPS)
    return roles


def _normalize_step_status(step: WorkflowStep) -> GlobalStatus:
    if step.normalized_status:
        return step.normalized_status
    if step.actual_done:
        return GlobalStatus.DONE
    if step.waiting_on_type:
        if step.waiting_on_type.value == "client":
            return GlobalStatus.BLOCKED_CLIENT
        if step.waiting_on_type.value == "internal":
            return GlobalStatus.BLOCKED_INTERNAL
        if step.waiting_on_type.value == "dependency":
            return GlobalStatus.BLOCKED_DEPENDENCY
    if step.actual_start:
        return GlobalStatus.IN_PROGRESS
    return GlobalStatus.NOT_STARTED


def _normalize_step_health(step: WorkflowStep) -> GlobalHealth:
    if step.normalized_health:
        return step.normalized_health
    st = _normalize_step_status(step)
    if st == GlobalStatus.NOT_STARTED:
        return GlobalHealth.NOT_STARTED
    if st in {GlobalStatus.BLOCKED_CLIENT, GlobalStatus.BLOCKED_INTERNAL, GlobalStatus.BLOCKED_DEPENDENCY, GlobalStatus.ON_HOLD}:
        return GlobalHealth.AT_RISK
    if st in {GlobalStatus.CANCELLED}:
        return GlobalHealth.OFF_TRACK
    return GlobalHealth.ON_TRACK


def _normalize_deliverable_status(status: DeliverableStatus) -> GlobalStatus:
    if status in {DeliverableStatus.PLANNED}:
        return GlobalStatus.NOT_STARTED
    if status in {
        DeliverableStatus.IN_PROGRESS,
        DeliverableStatus.AWAITING_INTERNAL_REVIEW,
        DeliverableStatus.INTERNAL_REVIEW_COMPLETE,
        DeliverableStatus.AWAITING_CLIENT_REVIEW,
        DeliverableStatus.CLIENT_CHANGES_REQUESTED,
        DeliverableStatus.APPROVED,
        DeliverableStatus.READY_TO_PUBLISH,
        DeliverableStatus.SCHEDULED_OR_PUBLISHED,
    }:
        return GlobalStatus.IN_PROGRESS
    return GlobalStatus.DONE


def _normalize_campaign_status(status: str | None) -> GlobalStatus:
    value = str(status or "").strip().lower()
    if value in {"not_started", "draft", "planned"}:
        return GlobalStatus.NOT_STARTED
    if value in {"in_progress", "active", "live"}:
        return GlobalStatus.IN_PROGRESS
    if value == "on_hold":
        return GlobalStatus.ON_HOLD
    if value == "blocked_client":
        return GlobalStatus.BLOCKED_CLIENT
    if value == "blocked_internal":
        return GlobalStatus.BLOCKED_INTERNAL
    if value == "blocked_dependency":
        return GlobalStatus.BLOCKED_DEPENDENCY
    if value in {"done", "complete", "completed"}:
        return GlobalStatus.DONE
    if value in {"cancelled", "canceled"}:
        return GlobalStatus.CANCELLED
    return GlobalStatus.NOT_STARTED


def _normalize_deliverable_health(status: DeliverableStatus) -> GlobalHealth:
    if status == DeliverableStatus.PLANNED:
        return GlobalHealth.NOT_STARTED
    if status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
        return GlobalHealth.AT_RISK
    return GlobalHealth.ON_TRACK


def _normalize_health(value: str | None) -> GlobalHealth:
    v = str(value or "").strip().lower()
    if v in {"not_started"}:
        return GlobalHealth.NOT_STARTED
    if v in {"on_track", "watch", "healthy"}:
        return GlobalHealth.ON_TRACK
    if v in {"at_risk"}:
        return GlobalHealth.AT_RISK
    if v in {"off_track", "critical"}:
        return GlobalHealth.OFF_TRACK
    return GlobalHealth.NOT_STARTED


def _deliverable_stage_from_record(deliverable: Deliverable) -> DeliverableStage:
    if deliverable.stage:
        return deliverable.stage
    dtype = deliverable.deliverable_type.value
    if dtype in {"kickoff_call", "interview_call"}:
        return DeliverableStage.PLANNING
    if dtype in {"report", "engagement_list", "lead_total"}:
        return DeliverableStage.REPORTING
    if dtype == "display_asset":
        return DeliverableStage.PROMOTION
    return DeliverableStage.PRODUCTION


def _step_module_type(_: WorkflowStep) -> str:
    return "step"


def _campaign_timeframe_from_milestones(milestones: list[Milestone]) -> tuple[str | None, str | None]:
    targets: list[date] = []
    for m in milestones:
        if m.current_target_date:
            targets.append(m.current_target_date)
        elif m.baseline_date:
            targets.append(m.baseline_date)
    if not targets:
        return None, None
    return min(targets).isoformat(), max(targets).isoformat()


def _assignment_role_lane(role_name: RoleName) -> RoleName:
    return RoleName.CC if role_name == RoleName.CCS else role_name


def _deliverable_matches_slot_lane(
    deliverable: Deliverable,
    slot_lane: RoleName,
    lanes_for_deliverable: set[RoleName],
) -> bool:
    default_role_value = str(deliverable.default_owner_role or "").strip().lower()
    if default_role_value:
        return default_role_value == slot_lane.value
    if slot_lane == RoleName.CC and deliverable.deliverable_type in {DeliverableType.ARTICLE, DeliverableType.VIDEO}:
        return True
    if slot_lane == RoleName.CM and deliverable.deliverable_type == DeliverableType.REPORT:
        return True
    return slot_lane in lanes_for_deliverable


def _participant_initials_for_step(
    step: WorkflowStep,
    efforts_by_step_id: dict[str, list[WorkflowStepEffort]],
    users_by_id: dict[str, User],
) -> list[str]:
    initials: list[str] = []
    owner_initials = _initials_for_user_id(step.next_owner_user_id, users_by_id)
    for effort in sorted(efforts_by_step_id.get(step.id, []), key=lambda e: (e.role_name.value, e.created_at)):
        if not effort.assigned_user_id:
            continue
        marker = _initials_for_user_id(effort.assigned_user_id, users_by_id)
        if marker == "--" or marker == owner_initials or marker in initials:
            continue
        initials.append(marker)
    return initials


def _delete_deliverable_graph(db: Session, deliverable_id: str) -> dict[str, int]:
    deleted = {
        "steps": 0,
        "step_efforts": 0,
        "reviews": 0,
        "review_windows": 0,
        "review_round_events": 0,
        "activity_logs": 0,
        "comments": 0,
        "notes": 0,
        "step_dependencies": 0,
        "deliverables": 0,
    }
    step_ids = db.scalars(
        select(WorkflowStep.id).where(
            WorkflowStep.linked_deliverable_id == deliverable_id
        )
    ).all()
    if step_ids:
        effort_res = db.execute(delete(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids)))
        deleted["step_efforts"] += int(effort_res.rowcount or 0)
        dep_res = db.execute(
            delete(WorkflowStepDependency).where(
                (WorkflowStepDependency.predecessor_step_id.in_(step_ids))
                | (WorkflowStepDependency.successor_step_id.in_(step_ids))
            )
        )
        deleted["step_dependencies"] += int(dep_res.rowcount or 0)
        step_res = db.execute(delete(WorkflowStep).where(WorkflowStep.id.in_(step_ids)))
        deleted["steps"] += int(step_res.rowcount or 0)

    reviews_res = db.execute(delete(Review).where(Review.deliverable_id == deliverable_id))
    deleted["reviews"] += int(reviews_res.rowcount or 0)
    windows_res = db.execute(delete(ReviewWindow).where(ReviewWindow.deliverable_id == deliverable_id))
    deleted["review_windows"] += int(windows_res.rowcount or 0)
    rounds_res = db.execute(delete(ReviewRoundEvent).where(ReviewRoundEvent.deliverable_id == deliverable_id))
    deleted["review_round_events"] += int(rounds_res.rowcount or 0)
    activity_res = db.execute(
        delete(ActivityLog).where(
            ActivityLog.entity_type == "deliverable",
            ActivityLog.entity_id == deliverable_id,
        )
    )
    deleted["activity_logs"] += int(activity_res.rowcount or 0)
    comments_res = db.execute(
        delete(Comment).where(
            Comment.entity_type == "deliverable",
            Comment.entity_id == deliverable_id,
        )
    )
    deleted["comments"] += int(comments_res.rowcount or 0)
    notes_res = db.execute(
        delete(Note).where(
            Note.entity_type == "deliverable",
            Note.entity_id == deliverable_id,
        )
    )
    deleted["notes"] += int(notes_res.rowcount or 0)
    deliverable_res = db.execute(delete(Deliverable).where(Deliverable.id == deliverable_id))
    deleted["deliverables"] += int(deliverable_res.rowcount or 0)
    return deleted


def _delete_campaign_graph(db: Session, campaign_id: str) -> dict[str, int]:
    deleted = {
        "deliverables": 0,
        "steps": 0,
        "step_efforts": 0,
        "step_dependencies": 0,
        "milestones": 0,
        "modules": 0,
        "assignments": 0,
        "system_risks": 0,
        "manual_risks": 0,
        "escalations": 0,
        "sow_change_requests": 0,
        "sow_change_approvals": 0,
        "benchmark_targets": 0,
        "performance_results": 0,
        "activity_logs": 0,
        "comments": 0,
        "notes": 0,
        "campaigns": 0,
    }

    deliverable_ids = db.scalars(select(Deliverable.id).where(Deliverable.campaign_id == campaign_id)).all()
    for deliverable_id in deliverable_ids:
        d = _delete_deliverable_graph(db, deliverable_id)
        deleted["deliverables"] += d["deliverables"]
        deleted["steps"] += d["steps"]
        deleted["step_efforts"] += d["step_efforts"]
        deleted["step_dependencies"] += d["step_dependencies"]
        deleted["activity_logs"] += d["activity_logs"]
        deleted["comments"] += d["comments"]
        deleted["notes"] += d["notes"]

    step_ids = db.scalars(
        select(WorkflowStep.id).where(
            WorkflowStep.campaign_id == campaign_id,
            WorkflowStep.linked_deliverable_id.is_(None),
        )
    ).all()
    if step_ids:
        effort_res = db.execute(delete(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids)))
        deleted["step_efforts"] += int(effort_res.rowcount or 0)
        dep_res = db.execute(
            delete(WorkflowStepDependency).where(
                (WorkflowStepDependency.predecessor_step_id.in_(step_ids))
                | (WorkflowStepDependency.successor_step_id.in_(step_ids))
            )
        )
        deleted["step_dependencies"] += int(dep_res.rowcount or 0)
        step_res = db.execute(delete(WorkflowStep).where(WorkflowStep.id.in_(step_ids)))
        deleted["steps"] += int(step_res.rowcount or 0)

    milestones_res = db.execute(delete(Milestone).where(Milestone.campaign_id == campaign_id))
    deleted["milestones"] += int(milestones_res.rowcount or 0)
    modules_res = db.execute(delete(ProductModule).where(ProductModule.campaign_id == campaign_id))
    deleted["modules"] += int(modules_res.rowcount or 0)
    assignments_res = db.execute(delete(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign_id))
    deleted["assignments"] += int(assignments_res.rowcount or 0)
    system_risk_ids = db.scalars(select(SystemRisk.id).where(SystemRisk.campaign_id == campaign_id)).all()
    manual_risk_ids = db.scalars(select(ManualRisk.id).where(ManualRisk.campaign_id == campaign_id)).all()
    if system_risk_ids:
        esc_sys_res = db.execute(
            delete(Escalation).where(
                Escalation.risk_type == "system",
                Escalation.risk_id.in_(system_risk_ids),
            )
        )
        deleted["escalations"] += int(esc_sys_res.rowcount or 0)
    if manual_risk_ids:
        esc_manual_res = db.execute(
            delete(Escalation).where(
                Escalation.risk_type == "manual",
                Escalation.risk_id.in_(manual_risk_ids),
            )
        )
        deleted["escalations"] += int(esc_manual_res.rowcount or 0)

    sys_risk_res = db.execute(delete(SystemRisk).where(SystemRisk.campaign_id == campaign_id))
    deleted["system_risks"] += int(sys_risk_res.rowcount or 0)
    manual_risk_res = db.execute(delete(ManualRisk).where(ManualRisk.campaign_id == campaign_id))
    deleted["manual_risks"] += int(manual_risk_res.rowcount or 0)

    sow_ids = db.scalars(select(SowChangeRequest.id).where(SowChangeRequest.campaign_id == campaign_id)).all()
    if sow_ids:
        sow_approvals_res = db.execute(delete(SowChangeApproval).where(SowChangeApproval.sow_change_request_id.in_(sow_ids)))
        deleted["sow_change_approvals"] += int(sow_approvals_res.rowcount or 0)
    sow_res = db.execute(delete(SowChangeRequest).where(SowChangeRequest.campaign_id == campaign_id))
    deleted["sow_change_requests"] += int(sow_res.rowcount or 0)

    benchmark_ids = db.scalars(select(BenchmarkTarget.id).where(BenchmarkTarget.campaign_id == campaign_id)).all()
    if benchmark_ids:
        perf_res = db.execute(delete(PerformanceResult).where(PerformanceResult.benchmark_target_id.in_(benchmark_ids)))
        deleted["performance_results"] += int(perf_res.rowcount or 0)
    benchmark_res = db.execute(delete(BenchmarkTarget).where(BenchmarkTarget.campaign_id == campaign_id))
    deleted["benchmark_targets"] += int(benchmark_res.rowcount or 0)

    activity_res = db.execute(
        delete(ActivityLog).where(
            ActivityLog.entity_type == "campaign",
            ActivityLog.entity_id == campaign_id,
        )
    )
    deleted["activity_logs"] += int(activity_res.rowcount or 0)
    comments_res = db.execute(
        delete(Comment).where(
            Comment.entity_type == "campaign",
            Comment.entity_id == campaign_id,
        )
    )
    deleted["comments"] += int(comments_res.rowcount or 0)
    notes_res = db.execute(
        delete(Note).where(
            Note.entity_type == "campaign",
            Note.entity_id == campaign_id,
        )
    )
    deleted["notes"] += int(notes_res.rowcount or 0)

    campaign_res = db.execute(delete(Campaign).where(Campaign.id == campaign_id))
    deleted["campaigns"] += int(campaign_res.rowcount or 0)
    return deleted


def _actor_has_control_permission(
    db: Session,
    actor: Any,
    control_id: str,
    fallback_allowed_roles: set[RoleName] | None = None,
) -> bool:
    if getattr(actor, "app_role", None) == AppAccessRole.SUPERADMIN:
        return True
    identity_payload = _identity_permissions_payload(db)
    if _is_app_control(control_id):
        app_rule = (identity_payload.get("app_control_permissions") or {}).get(control_id)
        if _identity_app_rule_allows(
            app_rule,
            seniority=actor.seniority,
            app_role=actor.app_role,
        ):
            return True
    else:
        campaign_rule = (identity_payload.get("campaign_control_permissions") or {}).get(control_id)
        if _identity_campaign_rule_allows(
            campaign_rule,
            team=actor.primary_team,
            seniority=actor.seniority,
            app_role=actor.app_role,
        ):
            return True
    identity_rule = (identity_payload.get("control_permissions") or {}).get(control_id)
    if _identity_rule_allows(identity_rule, team=actor.primary_team, seniority=actor.seniority, app_role=actor.app_role):
        return True
    perms = _role_permissions_payload(db).get("control_permissions") or {}
    configured = perms.get(control_id)
    if isinstance(configured, list):
        allowed_values = {str(v) for v in configured}
        if any(role.value in allowed_values for role in actor.roles):
            return True
    if fallback_allowed_roles:
        return bool(actor.roles.intersection(fallback_allowed_roles))
    return False


def _can_actor_approve_scope(db: Session, actor: Any) -> bool:
    if actor.app_role in {AppAccessRole.ADMIN, AppAccessRole.SUPERADMIN}:
        return True
    if _actor_has_control_permission(
        db,
        actor,
        "ops_approve_latest_deal",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.HEAD_SALES, RoleName.ADMIN},
    ):
        return True
    return actor.seniority == SeniorityLevel.LEADERSHIP and actor.primary_team in {TeamName.SALES, TeamName.CLIENT_SERVICES}


def _can_actor_generate_campaigns(db: Session, actor: Any) -> bool:
    if actor.app_role in {AppAccessRole.ADMIN, AppAccessRole.SUPERADMIN}:
        return True
    if _actor_has_control_permission(
        db,
        actor,
        "generate_latest_campaigns",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        return True
    return actor.seniority == SeniorityLevel.LEADERSHIP and actor.primary_team == TeamName.CLIENT_SERVICES


@router.post("/deals", response_model=DealOut)
@router.post("/scopes", response_model=DealOut)
def create_deal(payload: DealCreateIn, actor_user_id: str, db: Session = Depends(get_db)) -> DealOut:
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.AM, RoleName.ADMIN})
    if payload.am_user_id != actor_user_id and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor must match am_user_id unless admin")

    try:
        deal = DealService(db).create_deal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    client = db.get(Client, deal.client_id)
    return DealOut(
        id=deal.display_id,
        status=deal.status.value,
        client_name=client.name if client else None,
        brand_publication=deal.brand_publication.value,
    )


@router.post("/deals/{deal_id}/submit", response_model=DealOut)
@router.post("/scopes/{deal_id}/submit", response_model=DealOut)
def submit_deal(deal_id: str, actor_user_id: str, db: Session = Depends(get_db)) -> DealOut:
    deal = _resolve_by_identifier(db, Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="scope not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_deal_owner_or_roles(actor, deal, {RoleName.ADMIN, RoleName.HEAD_OPS})

    DealService(db).submit_deal(deal)
    db.commit()
    client = db.get(Client, deal.client_id)
    return DealOut(
        id=deal.display_id,
        status=deal.status.value,
        client_name=client.name if client else None,
        brand_publication=deal.brand_publication.value,
    )


@router.post("/deals/{deal_id}/ops-approve", response_model=DealOut)
@router.post("/scopes/{deal_id}/ops-approve", response_model=DealOut)
def ops_approve_deal(deal_id: str, payload: OpsApproveIn, actor_user_id: str, db: Session = Depends(get_db)) -> DealOut:
    deal = _resolve_by_identifier(db, Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="scope not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    if not _can_actor_approve_scope(db, actor):
        raise HTTPException(status_code=403, detail="insufficient permissions to approve scope")

    if not payload.head_ops_user_id:
        payload.head_ops_user_id = actor_user_id
    deal = DealService(db).ops_approve(deal, payload)
    db.commit()
    client = db.get(Client, deal.client_id)
    return DealOut(
        id=deal.display_id,
        status=deal.status.value,
        client_name=client.name if client else None,
        brand_publication=deal.brand_publication.value,
    )


@router.post("/deals/{deal_id}/generate-campaigns", response_model=list[CampaignOut])
@router.post("/scopes/{deal_id}/generate-campaigns", response_model=list[CampaignOut])
def generate_campaigns(deal_id: str, actor_user_id: str, db: Session = Depends(get_db)) -> list[CampaignOut]:
    deal = _resolve_by_identifier(db, Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="scope not found")
    if deal.status != DealStatus.READINESS_PASSED:
        raise HTTPException(status_code=400, detail="scope must pass operational readiness gate")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    if not _can_actor_generate_campaigns(db, actor):
        raise HTTPException(status_code=403, detail="insufficient permissions to generate campaigns")

    try:
        generated = CampaignGenerationService(db).generate_for_deal(deal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    deal.status = DealStatus.CAMPAIGNS_GENERATED
    db.commit()

    return [
        CampaignOut(
            id=c.display_id,
            type=c.campaign_type.value,
            tier=c.tier,
            title=c.title,
        )
        for c in generated
    ]


@router.get("/campaigns/health")
def list_campaigns_health(
    owner: str | None = None,
    status: str | None = None,
    publication: str | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    payload = CampaignHealthService(db).evaluate_many(
        campaigns=campaigns,
        owner=owner,
        status=status,
        publication=publication,
        limit=limit,
        offset=offset,
    )
    return payload


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    return {
        "id": campaign.display_id,
        "title": campaign.title,
        "type": campaign.campaign_type.value,
        "tier": campaign.tier,
        "template_version_id": campaign.template_version_id,
    }


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, actor_user_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    allowed = _actor_has_control_permission(
        db,
        actor,
        "delete_campaign",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="not permitted to delete campaign")

    deleted = _delete_campaign_graph(db, campaign.id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_deleted",
            meta_json={"campaign_id": campaign.display_id, "deleted_counts": deleted},
        )
    )
    db.commit()
    return {"deleted": True, "campaign_id": campaign.display_id, "counts": deleted}


@router.get("/deals")
@router.get("/scopes")
def list_deals(
    limit: int = 25,
    offset: int = 0,
    q: str | None = None,
    actor_user_id: str | None = None,
    db: Session = Depends(get_db),
):
    actor = None
    full_visibility = True
    if actor_user_id:
        actor = AuthzService(db).actor(actor_user_id)
        full_visibility = _actor_has_full_scope_campaign_visibility(actor)

    deals = db.scalars(select(Deal).order_by(Deal.created_at.desc())).all()
    campaigns = db.scalars(select(Campaign)).all()
    campaigns_by_deal: dict[str, list[Campaign]] = {}
    for c in campaigns:
        campaigns_by_deal.setdefault(c.deal_id, []).append(c)
    assignments = db.scalars(select(CampaignAssignment)).all()
    assignments_by_campaign: dict[str, list[CampaignAssignment]] = {}
    for a in assignments:
        assignments_by_campaign.setdefault(a.campaign_id, []).append(a)
    milestones = db.scalars(select(Milestone)).all()
    milestones_by_campaign: dict[str, list[Milestone]] = {}
    for m in milestones:
        milestones_by_campaign.setdefault(m.campaign_id, []).append(m)
    all_deliverables = db.scalars(select(Deliverable)).all()
    deliverables_by_campaign: dict[str, list[Deliverable]] = {}
    for d in all_deliverables:
        if d.campaign_id:
            deliverables_by_campaign.setdefault(d.campaign_id, []).append(d)
    all_steps = db.scalars(select(WorkflowStep)).all()
    steps_by_campaign: dict[str, list[WorkflowStep]] = {}
    for s in all_steps:
        if s.campaign_id:
            steps_by_campaign.setdefault(s.campaign_id, []).append(s)
        elif _step_linked_deliverable(s):
            parent = next((d for d in all_deliverables if d.id == _step_linked_deliverable(s) and d.campaign_id), None)
            if parent:
                steps_by_campaign.setdefault(parent.campaign_id, []).append(s)
    step_ids = [s.id for s in all_steps]
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if step_ids:
        for e in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts_by_step.setdefault(e.workflow_step_id, []).append(e)
    timeline_health = TimelineHealthService(db)
    clients = {c.id: c for c in db.scalars(select(Client)).all()}
    contacts_by_client: dict[str, list[ClientContact]] = {}
    for contact in db.scalars(select(ClientContact).order_by(ClientContact.created_at.asc())).all():
        contacts_by_client.setdefault(contact.client_id, []).append(contact)
    attachments_by_deal: dict[str, list[DealAttachment]] = {}
    for attachment in db.scalars(select(DealAttachment).order_by(DealAttachment.created_at.desc())).all():
        attachments_by_deal.setdefault(attachment.deal_id, []).append(attachment)
    product_lines = db.scalars(select(DealProductLine)).all()
    lines_by_deal: dict[str, list[DealProductLine]] = {}
    for line in product_lines:
        lines_by_deal.setdefault(line.deal_id, []).append(line)
    assignment_user_ids = {
        assignment.user_id
        for assignment_list in assignments_by_campaign.values()
        for assignment in assignment_list
        if assignment.user_id
    }
    am_user_ids = {deal.am_user_id for deal in deals if deal.am_user_id}
    staffing_user_ids = {
        user_id
        for deal in deals
        for user_id in (deal.assigned_cm_user_id, deal.assigned_cc_user_id, deal.assigned_ccs_user_id)
        if user_id
    }
    deliverable_owner_user_ids = {
        d.owner_user_id
        for rows in deliverables_by_campaign.values()
        for d in rows
        if d.owner_user_id
    }
    step_owner_user_ids = {
        s.next_owner_user_id
        for rows in steps_by_campaign.values()
        for s in rows
        if s.next_owner_user_id
    }
    user_ids = sorted(
        assignment_user_ids
        .union(am_user_ids)
        .union(staffing_user_ids)
        .union(deliverable_owner_user_ids)
        .union(step_owner_user_ids)
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    assignment_user_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in assignments_by_campaign.items():
        assignment_user_ids_by_campaign[campaign_id] = {r.user_id for r in rows if r.user_id}
    deliverable_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in deliverables_by_campaign.items():
        deliverable_owner_ids_by_campaign[campaign_id] = {d.owner_user_id for d in rows if d.owner_user_id}
    step_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in steps_by_campaign.items():
        step_owner_ids_by_campaign[campaign_id] = {s.next_owner_user_id for s in rows if s.next_owner_user_id}

    def _campaign_visible_for_actor(campaign: Campaign) -> bool:
        if full_visibility or not actor:
            return True
        campaign_user_ids = (
            assignment_user_ids_by_campaign.get(campaign.id, set())
            .union(deliverable_owner_ids_by_campaign.get(campaign.id, set()))
            .union(step_owner_ids_by_campaign.get(campaign.id, set()))
        )
        if actor.seniority == SeniorityLevel.MANAGER:
            return any(
                (uid in users_by_id) and (users_by_id[uid].primary_team == actor.primary_team)
                for uid in campaign_user_ids
            )
        return actor.user_id in campaign_user_ids

    def _deal_visible_for_actor(deal: Deal, child_campaigns: list[Campaign]) -> bool:
        if full_visibility or not actor:
            return True
        if actor.seniority == SeniorityLevel.MANAGER:
            deal_user_ids = {
                deal.am_user_id,
                deal.assigned_cm_user_id,
                deal.assigned_cc_user_id,
                deal.assigned_ccs_user_id,
            }
            deal_user_ids = {uid for uid in deal_user_ids if uid}
            team_matches_deal = any(
                (uid in users_by_id) and (users_by_id[uid].primary_team == actor.primary_team)
                for uid in deal_user_ids
            )
            return team_matches_deal or any(_campaign_visible_for_actor(c) for c in child_campaigns)
        return (
            actor.user_id == deal.am_user_id
            or actor.user_id in {deal.assigned_cm_user_id, deal.assigned_cc_user_id, deal.assigned_ccs_user_id}
            or any(_campaign_visible_for_actor(c) for c in child_campaigns)
        )
    all_items = []
    for d in deals:
        deal_campaigns = campaigns_by_deal.get(d.id, [])
        if not _deal_visible_for_actor(d, deal_campaigns):
            continue
        campaign_evals: list[tuple[Campaign, Any]] = []
        for c in deal_campaigns:
            c_eval, _ = timeline_health.evaluate_campaign(
                campaign=c,
                deliverables=deliverables_by_campaign.get(c.id, []),
                steps=steps_by_campaign.get(c.id, []),
                efforts_by_step_id=efforts_by_step,
                assignments=assignments_by_campaign.get(c.id, []),
                stages=db.scalars(select(Stage).where(Stage.campaign_id == c.id)).all(),
            )
            campaign_evals.append((c, c_eval))
        scope_campaigns = []
        for c, c_eval in sorted(
            campaign_evals,
            key=lambda row: (
                row[0].planned_start_date or date.max,
                row[0].created_at or datetime.max,
            ),
        ):
            milestone_window = _campaign_timeframe_from_milestones(milestones_by_campaign.get(c.id, []))
            scope_campaigns.append(
                {
                    "id": c.display_id,
                    "campaign_internal_id": c.id,
                    "type": c.campaign_type.value,
                    "tier": c.tier,
                    "title": c.title,
                    "scope_id": d.display_id,
                    "status": _normalize_campaign_status(c.status).value,
                    "health": str(c_eval.health or "not_started"),
                    "health_reason": c_eval.health_reason,
                    "buffer_working_days_remaining": c_eval.buffer_working_days_remaining,
                    "is_not_due": c_eval.is_not_due,
                    "is_demand_sprint": c.is_demand_sprint,
                    "demand_sprint_number": c.demand_sprint_number,
                    "demand_track": c.demand_track,
                    "sprint_label": (
                        f"S{c.demand_sprint_number}"
                        if c.is_demand_sprint and c.demand_sprint_number
                        else None
                    ),
                    "timeframe_start": c.planned_start_date.isoformat() if c.planned_start_date else milestone_window[0],
                    "timeframe_due": c.planned_end_date.isoformat() if c.planned_end_date else milestone_window[1],
                    "assigned_users": [
                        {
                            "user_id": assignment.user_id,
                            "name": users_by_id.get(assignment.user_id).full_name if users_by_id.get(assignment.user_id) else None,
                            "initials": _initials_for_user_id(assignment.user_id, users_by_id),
                            "role": assignment.role_name.value,
                        }
                        for assignment in sorted(assignments_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                    ],
                    "assigned_user_initials": [
                        _initials_for_user_id(assignment.user_id, users_by_id)
                        for assignment in sorted(assignments_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                        if assignment.user_id
                    ],
                    "deliverables_summary": {"total": 0, "not_started": 0, "in_progress": 0, "done": 0},
                    "work_summary": {"total": 0, "not_started": 0, "in_progress": 0, "done": 0},
                    "deliverables": [],
                    "work_steps": [],
                }
            )
        scope_eval = timeline_health.evaluate_scope(d, campaign_evals)
        scope_contacts = contacts_by_client.get(d.client_id, [])
        primary_contact = scope_contacts[0] if scope_contacts else None
        scope_attachments = attachments_by_deal.get(d.id, [])
        am_user = users_by_id.get(d.am_user_id)
        all_items.append({
                "id": d.display_id,
                "client_name": clients.get(d.client_id).name if clients.get(d.client_id) else None,
                "brand_publication": d.brand_publication.value,
                "status": d.status.value,
                "health": scope_eval.health,
                "health_reason": scope_eval.health_reason,
                "buffer_working_days_remaining": scope_eval.buffer_working_days_remaining,
                "is_not_due": scope_eval.is_not_due,
                "sow_start_date": d.sow_start_date.isoformat() if d.sow_start_date else None,
                "sow_end_date": d.sow_end_date.isoformat() if d.sow_end_date else None,
                "icp": d.icp,
                "campaign_objective": d.campaign_objective,
                "messaging_positioning": d.messaging_positioning,
                "commercial_notes": d.commercial_notes,
                "product_lines": [
                    {
                        "product_type": line.product_type.value,
                        "tier": line.tier,
                    }
                    for line in lines_by_deal.get(d.id, [])
                ],
                "am_user": {
                    "user_id": d.am_user_id,
                    "name": am_user.full_name if am_user else None,
                    "initials": _initials_for_user_id(d.am_user_id, users_by_id),
                },
                "assigned_cm_user_id": d.assigned_cm_user_id,
                "assigned_cc_user_id": d.assigned_cc_user_id,
                "assigned_ccs_user_id": d.assigned_ccs_user_id,
                "client_contact_name": primary_contact.name if primary_contact else None,
                "client_contact_email": primary_contact.email if primary_contact else None,
                "attachments": [
                    {
                        "file_name": attachment.file_name,
                        "storage_key": attachment.storage_key,
                    }
                    for attachment in scope_attachments
                ],
                "campaigns": scope_campaigns,
                "readiness_passed": d.readiness_passed,
                "created_at": d.created_at.isoformat(),
            })
    if q:
        needle = q.strip().lower()
        all_items = [
            item
            for item in all_items
            if needle in " ".join(
                [
                    item["id"] or "",
                    item["client_name"] or "",
                    item["brand_publication"] or "",
                    item["status"] or "",
                    item["campaign_objective"] or "",
                ]
            ).lower()
        ]
    total = len(all_items)
    items = all_items[offset : offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/publications")
def list_publications(db: Session = Depends(get_db)):
    pubs = db.scalars(select(Publication).order_by(Publication.name.asc())).all()
    return {"items": [{"id": p.id, "name": p.name.value} for p in pubs]}


@router.get("/campaigns")
def list_campaigns(
    limit: int = 25,
    offset: int = 0,
    q: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    actor_user_id: str | None = None,
    db: Session = Depends(get_db),
):
    actor = None
    full_visibility = True
    if actor_user_id:
        actor = AuthzService(db).actor(actor_user_id)
        full_visibility = _actor_has_full_scope_campaign_visibility(actor)

    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    deals_by_id = {d.id: d for d in db.scalars(select(Deal)).all()}
    assignments = db.scalars(select(CampaignAssignment)).all()
    campaign_ids = [c.id for c in campaigns]
    deliverables_by_campaign: dict[str, list[Deliverable]] = {}
    workflow_steps_by_campaign: dict[str, list[WorkflowStep]] = {}
    step_efforts_by_step_id: dict[str, list[WorkflowStepEffort]] = {}
    if campaign_ids:
        deliverable_rows = db.scalars(select(Deliverable).where(Deliverable.campaign_id.in_(campaign_ids))).all()
        for d in deliverable_rows:
            deliverables_by_campaign.setdefault(d.campaign_id, []).append(d)
        workflow_rows = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id.in_(campaign_ids))).all()
        for s in workflow_rows:
            workflow_steps_by_campaign.setdefault(s.campaign_id, []).append(s)
        step_ids = [s.id for s in workflow_rows]
        if step_ids:
            effort_rows = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
            for e in effort_rows:
                step_efforts_by_step_id.setdefault(e.workflow_step_id, []).append(e)
    owners_by_campaign: dict[str, set[str]] = {}
    assignment_rows_by_campaign: dict[str, list[CampaignAssignment]] = {}
    for a in assignments:
        owners_by_campaign.setdefault(a.campaign_id, set()).add(a.user_id)
        assignment_rows_by_campaign.setdefault(a.campaign_id, []).append(a)

    milestones_by_campaign: dict[str, list[Milestone]] = {}
    if campaign_ids:
        milestone_rows = db.scalars(select(Milestone).where(Milestone.campaign_id.in_(campaign_ids))).all()
        for m in milestone_rows:
            milestones_by_campaign.setdefault(m.campaign_id, []).append(m)
    timeframe_by_campaign = {
        cid: _campaign_timeframe_from_milestones(rows)
        for cid, rows in milestones_by_campaign.items()
    }

    user_ids = sorted(
        {
            a.user_id
            for a in assignments
            if a.user_id
        }
        .union(
            {
                s.next_owner_user_id
                for rows in workflow_steps_by_campaign.values()
                for s in rows
                if s.next_owner_user_id
            }
        )
        .union(
            {
                e.assigned_user_id
                for rows in step_efforts_by_step_id.values()
                for e in rows
                if e.assigned_user_id
            }
        )
        .union(
            {
                d.owner_user_id
                for rows in deliverables_by_campaign.values()
                for d in rows
                if d.owner_user_id
            }
        )
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    assignment_user_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in assignment_rows_by_campaign.items():
        assignment_user_ids_by_campaign[campaign_id] = {r.user_id for r in rows if r.user_id}
    deliverable_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in deliverables_by_campaign.items():
        deliverable_owner_ids_by_campaign[campaign_id] = {d.owner_user_id for d in rows if d.owner_user_id}
    step_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in workflow_steps_by_campaign.items():
        step_owner_ids_by_campaign[campaign_id] = {s.next_owner_user_id for s in rows if s.next_owner_user_id}

    def _campaign_visible_for_actor(campaign: Campaign) -> bool:
        if full_visibility or not actor:
            return True
        campaign_user_ids = (
            assignment_user_ids_by_campaign.get(campaign.id, set())
            .union(deliverable_owner_ids_by_campaign.get(campaign.id, set()))
            .union(step_owner_ids_by_campaign.get(campaign.id, set()))
        )
        if actor.seniority == SeniorityLevel.MANAGER:
            return any(
                (uid in users_by_id) and (users_by_id[uid].primary_team == actor.primary_team)
                for uid in campaign_user_ids
            )
        return actor.user_id in campaign_user_ids

    timeline_health = TimelineHealthService(db)
    health_by_campaign: dict[str, dict] = {}
    derived_stage_by_campaign: dict[str, str] = {}
    for c in campaigns:
        c_deliverables = deliverables_by_campaign.get(c.id, [])
        c_steps = workflow_steps_by_campaign.get(c.id, [])
        c_assignments = assignment_rows_by_campaign.get(c.id, [])
        eval_result, derived_stage = timeline_health.evaluate_campaign(
            campaign=c,
            deliverables=c_deliverables,
            steps=c_steps,
            efforts_by_step_id=step_efforts_by_step_id,
            assignments=c_assignments,
        )
        health_by_campaign[c.id] = {
            "overall_status": eval_result.health,
            "health_reason": eval_result.health_reason,
            "buffer_working_days_remaining": eval_result.buffer_working_days_remaining,
            "is_not_due": eval_result.is_not_due,
        }
        derived_stage_by_campaign[c.id] = derived_stage

    all_items = [
            {
                "id": c.display_id,
                "campaign_internal_id": c.id,
                "type": c.campaign_type.value,
                "tier": c.tier,
                "title": c.title,
                "scope_id": deals_by_id.get(c.deal_id).display_id if deals_by_id.get(c.deal_id) else None,
                "status": _normalize_campaign_status(c.status).value,
                "is_demand_sprint": c.is_demand_sprint,
                "demand_sprint_number": c.demand_sprint_number,
                "demand_track": c.demand_track,
                "sprint_label": (f"S{c.demand_sprint_number}" if c.is_demand_sprint and c.demand_sprint_number else None),
                "template_version_id": c.template_version_id,
                "owner_user_ids": sorted(list(owners_by_campaign.get(c.id, set()))),
                "module_type": "campaign",
                "health": str((health_by_campaign.get(c.id) or {}).get("overall_status") or "not_started"),
                "health_reason": (health_by_campaign.get(c.id) or {}).get("health_reason"),
                "buffer_working_days_remaining": (health_by_campaign.get(c.id) or {}).get("buffer_working_days_remaining"),
                "is_not_due": bool((health_by_campaign.get(c.id) or {}).get("is_not_due")),
                "timeframe_start": (c.planned_start_date.isoformat() if c.planned_start_date else (timeframe_by_campaign.get(c.id) or (None, None))[0]),
                "timeframe_due": (c.planned_end_date.isoformat() if c.planned_end_date else (timeframe_by_campaign.get(c.id) or (None, None))[1]),
                "derived_stage": derived_stage_by_campaign.get(c.id, "not_started"),
                "assigned_users": [
                    {
                        "user_id": a.user_id,
                        "name": users_by_id.get(a.user_id).full_name if users_by_id.get(a.user_id) else None,
                        "initials": _initials_for_user_id(a.user_id, users_by_id),
                        "role": a.role_name.value,
                    }
                    for a in sorted(assignment_rows_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                ],
                "assigned_user_initials": [
                    _initials_for_user_id(a.user_id, users_by_id)
                    for a in sorted(assignment_rows_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                    if a.user_id
                ],
                "campaign_name": c.title,
                "campaign_status": _normalize_campaign_status(c.status).value,
                "campaign_health": str((health_by_campaign.get(c.id) or {}).get("overall_status") or "not_started"),
                "deliverables_summary": {
                    "total": len(deliverables_by_campaign.get(c.id, [])),
                    "not_started": len(
                        [
                            d
                            for d in deliverables_by_campaign.get(c.id, [])
                            if _normalize_deliverable_status(d.status) == GlobalStatus.NOT_STARTED
                        ]
                    ),
                    "in_progress": len(
                        [
                            d
                            for d in deliverables_by_campaign.get(c.id, [])
                            if _normalize_deliverable_status(d.status) in {
                                GlobalStatus.IN_PROGRESS,
                                GlobalStatus.ON_HOLD,
                                GlobalStatus.BLOCKED_CLIENT,
                                GlobalStatus.BLOCKED_INTERNAL,
                                GlobalStatus.BLOCKED_DEPENDENCY,
                            }
                        ]
                    ),
                    "done": len(
                        [
                            d
                            for d in deliverables_by_campaign.get(c.id, [])
                            if _normalize_deliverable_status(d.status) == GlobalStatus.DONE
                        ]
                    ),
                },
                "deliverables": [
                    {
                        "id": d.display_id,
                        "title": d.title,
                        "status": _normalize_deliverable_status(d.status).value,
                        "delivery_status": d.status.value,
                        "health": timeline_health.evaluate_deliverable(
                            deliverable=d,
                            campaign=c,
                            steps=[s for s in workflow_steps_by_campaign.get(c.id, []) if _step_linked_deliverable(s) == d.id],
                            efforts_by_step_id=step_efforts_by_step_id,
                        ).health,
                        "current_due": d.current_due.isoformat() if d.current_due else None,
                        "current_start": d.current_start.isoformat() if d.current_start else None,
                        "stage": _deliverable_stage_from_record(d).value,
                        "owner_user_id": d.owner_user_id,
                        "owner_initials": _initials_for_user_id(d.owner_user_id, users_by_id),
                        "campaign_name": c.title,
                    }
                    for d in sorted(
                        deliverables_by_campaign.get(c.id, []),
                        key=lambda x: (x.current_due or date.max, x.created_at),
                    )
                ],
                "work_summary": {
                    "total": len(workflow_steps_by_campaign.get(c.id, [])),
                    "not_started": len(
                        [
                            s
                            for s in workflow_steps_by_campaign.get(c.id, [])
                            if _normalize_step_status(s) == GlobalStatus.NOT_STARTED
                        ]
                    ),
                    "in_progress": len(
                        [
                            s
                            for s in workflow_steps_by_campaign.get(c.id, [])
                            if _normalize_step_status(s)
                            in {
                                GlobalStatus.IN_PROGRESS,
                                GlobalStatus.ON_HOLD,
                                GlobalStatus.BLOCKED_CLIENT,
                                GlobalStatus.BLOCKED_INTERNAL,
                                GlobalStatus.BLOCKED_DEPENDENCY,
                            }
                        ]
                    ),
                    "done": len(
                        [
                            s
                            for s in workflow_steps_by_campaign.get(c.id, [])
                            if _normalize_step_status(s) == GlobalStatus.DONE
                        ]
                    ),
                },
                "work_steps": [
                    {
                        "id": s.display_id,
                        "name": s.name,
                        "module_type": "step",
                        "stage": (
                            (
                                str(s.stage_name).strip().lower()
                                if s.stage_name and str(s.stage_name).strip().lower() in {"planning", "production", "promotion", "reporting"}
                                else (
                                    _deliverable_stage_from_record(
                                        next(
                                            (d for d in deliverables_by_campaign.get(c.id, []) if d.id == _step_linked_deliverable(s)),
                                            None,
                                        )
                                    ).value
                                    if _step_linked_deliverable(s)
                                    and next(
                                        (d for d in deliverables_by_campaign.get(c.id, []) if d.id == _step_linked_deliverable(s)),
                                        None,
                                    )
                                    else (
                                        "planning" if s.campaign_id and not _step_linked_deliverable(s) else "production"
                                    )
                                )
                            )
                        ),
                        "status": _normalize_step_status(s).value,
                        "health": timeline_health.evaluate_step(s, campaign=c).health,
                        "current_start": s.current_start.isoformat() if s.current_start else None,
                        "current_due": s.current_due.isoformat() if s.current_due else None,
                        "next_owner_user_id": s.next_owner_user_id,
                        "owner_initials": _initials_for_user_id(s.next_owner_user_id, users_by_id),
                        "participant_initials": _participant_initials_for_step(s, step_efforts_by_step_id, users_by_id),
                        "deliverable_title": next(
                            (d.title for d in deliverables_by_campaign.get(c.id, []) if d.id == _step_linked_deliverable(s)),
                            None,
                        ),
                    }
                    for s in sorted(
                        workflow_steps_by_campaign.get(c.id, []),
                        key=lambda x: (x.current_due or date.max, x.created_at),
                    )
                ],
                "created_at": c.created_at.isoformat(),
            }
        for c in campaigns
        if _campaign_visible_for_actor(c)
    ]
    if status:
        needle_status = status.strip().lower()
        all_items = [
            i
            for i in all_items
            if i["status"] == needle_status or str(i.get("delivery_status", "")).lower() == needle_status
        ]
    if owner:
        all_items = [i for i in all_items if owner in i["owner_user_ids"]]
    if q:
        needle = q.strip().lower()
        all_items = [
            i
            for i in all_items
            if needle in " ".join([i["id"], i["title"], i["type"], i["tier"], i["status"]]).lower()
        ]
    total = len(all_items)
    items = all_items[offset : offset + limit]
    for i in items:
        i.pop("campaign_internal_id", None)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.patch("/campaigns/{campaign_id}/assignments")
def update_campaign_assignments(campaign_id: str, payload: CampaignAssignmentsUpdateIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_assignments",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    updates = [
        (RoleName.AM, payload.am_user_id),
        (RoleName.CM, payload.cm_user_id),
        (RoleName.CC, payload.cc_user_id),
        (RoleName.CCS, payload.ccs_user_id),
        (RoleName.DN, payload.dn_user_id),
        (RoleName.MM, payload.mm_user_id),
    ]

    required_team_by_slot = {
        RoleName.AM: TeamName.SALES,
        RoleName.CM: TeamName.CLIENT_SERVICES,
        RoleName.CC: TeamName.EDITORIAL,
        RoleName.CCS: TeamName.EDITORIAL,
        RoleName.DN: TeamName.MARKETING,
        RoleName.MM: TeamName.MARKETING,
    }

    by_role = {
        a.role_name: a
        for a in db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    }
    old_assignment_by_role: dict[RoleName, str | None] = {
        role_name: (by_role.get(role_name).user_id if by_role.get(role_name) else None)
        for role_name, _ in updates
    }

    for role_name, user_id in updates:
        if user_id:
            exists = db.get(User, user_id)
            if not exists:
                raise HTTPException(status_code=400, detail=f"user not found for role {role_name.value}")
            required_team = required_team_by_slot.get(role_name)
            if required_team and exists.primary_team != required_team:
                raise HTTPException(
                    status_code=400,
                    detail=f"user must be in team {required_team.value} for role {role_name.value}",
                )
        existing = by_role.get(role_name)
        if user_id:
            if existing:
                existing.user_id = user_id
            else:
                db.add(CampaignAssignment(campaign_id=campaign.id, role_name=role_name, user_id=user_id))
        elif existing:
            db.delete(existing)

    changed_slots: list[dict[str, str | None]] = []
    for role_name, new_user_id in updates:
        old_user_id = old_assignment_by_role.get(role_name)
        if old_user_id != new_user_id:
            changed_slots.append(
                {
                    "slot": role_name.value,
                    "old_user_id": old_user_id,
                    "new_user_id": new_user_id,
                }
            )

    cascade_deliverables_updated = 0
    cascade_steps_updated = 0
    cascade_by_slot: dict[str, dict[str, int]] = {}
    if payload.cascade_owner_updates and changed_slots:
        campaign_deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
        deliverable_ids = [d.id for d in campaign_deliverables]
        if deliverable_ids:
            relevant_steps = db.scalars(
                select(WorkflowStep).where(
                    or_(
                        WorkflowStep.campaign_id == campaign.id,
                        WorkflowStep.linked_deliverable_id.in_(deliverable_ids),
                    )
                )
            ).all()
        else:
            relevant_steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()

        role_lanes_by_deliverable: dict[str, set[RoleName]] = {}
        for step in relevant_steps:
            linked = _step_linked_deliverable(step)
            if not linked:
                continue
            role_lanes_by_deliverable.setdefault(linked, set()).add(_assignment_role_lane(step.owner_role))

        for slot_change in changed_slots:
            slot = str(slot_change.get("slot") or "")
            new_user_id = slot_change.get("new_user_id")
            slot_role = RoleName(slot)
            slot_lane = _assignment_role_lane(slot_role)
            slot_deliverables_updated = 0
            slot_steps_updated = 0

            for deliverable in campaign_deliverables:
                lanes = role_lanes_by_deliverable.get(deliverable.id, set())
                if not _deliverable_matches_slot_lane(deliverable, slot_lane, lanes):
                    continue
                if deliverable.owner_user_id == new_user_id:
                    continue
                deliverable.owner_user_id = new_user_id
                slot_deliverables_updated += 1

            for step in relevant_steps:
                if _assignment_role_lane(step.owner_role) != slot_lane:
                    continue
                if step.next_owner_user_id == new_user_id:
                    continue
                step.next_owner_user_id = new_user_id
                slot_steps_updated += 1

            if slot_deliverables_updated or slot_steps_updated:
                cascade_by_slot[slot] = {
                    "deliverables": slot_deliverables_updated,
                    "steps": slot_steps_updated,
                }
            cascade_deliverables_updated += slot_deliverables_updated
            cascade_steps_updated += slot_steps_updated

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_assignments_updated",
            meta_json={
                "campaign_id": campaign.display_id,
                "am_user_id": payload.am_user_id,
                "cm_user_id": payload.cm_user_id,
                "cc_user_id": payload.cc_user_id,
                "ccs_user_id": payload.ccs_user_id,
                "dn_user_id": payload.dn_user_id,
                "mm_user_id": payload.mm_user_id,
                "changed_slots": changed_slots,
                "cascade_owner_updates": bool(payload.cascade_owner_updates),
                "cascade_counts": {
                    "deliverables": cascade_deliverables_updated,
                    "steps": cascade_steps_updated,
                    "by_slot": cascade_by_slot,
                },
            },
        )
    )

    assignment_by_role = {
        role_name: user_id for role_name, user_id in updates if user_id
    }
    campaign_steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()
    step_ids = [s.id for s in campaign_steps]
    if step_ids:
        step_efforts = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
        for effort in step_efforts:
            effort.assigned_user_id = assignment_by_role.get(effort.role_name)

    db.commit()

    refreshed = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    return {
        "campaign_id": campaign.display_id,
        "assignments": {a.role_name.value: a.user_id for a in refreshed},
        "cascade_applied": bool(payload.cascade_owner_updates),
        "updated_deliverables_count": int(cascade_deliverables_updated),
        "updated_steps_count": int(cascade_steps_updated),
        "updated_by_slot": cascade_by_slot,
    }


@router.patch("/campaigns/{campaign_id}/status")
def update_campaign_status(campaign_id: str, payload: CampaignStatusUpdateIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_status",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    old_status = _normalize_campaign_status(campaign.status).value
    new_status = _normalize_campaign_status(payload.status).value
    if new_status == old_status:
        return {"campaign_id": campaign.display_id, "status": old_status}

    campaign.status = new_status
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_status_updated",
            meta_json={
                "campaign_id": campaign.display_id,
                "old_status": old_status,
                "new_status": new_status,
            },
        )
    )
    db.commit()
    return {"campaign_id": campaign.display_id, "status": new_status}


@router.patch("/campaigns/{campaign_id}/dates")
def update_campaign_dates(campaign_id: str, payload: CampaignDatesUpdateIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_dates",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")
    if not payload.planned_start_iso and not payload.planned_end_iso:
        raise HTTPException(status_code=400, detail="at least one date is required")

    calendar = build_default_working_calendar()
    old_start = campaign.planned_start_date
    old_end = campaign.planned_end_date

    if payload.planned_start_iso:
        try:
            requested_start = date.fromisoformat(payload.planned_start_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid planned_start_iso; expected YYYY-MM-DD") from exc
        campaign.planned_start_date = calendar.next_working_day_on_or_after(requested_start)

    if payload.planned_end_iso:
        try:
            requested_end = date.fromisoformat(payload.planned_end_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid planned_end_iso; expected YYYY-MM-DD") from exc
        campaign.planned_end_date = calendar.next_working_day_on_or_after(requested_end)

    if campaign.planned_start_date and campaign.planned_end_date and campaign.planned_end_date < campaign.planned_start_date:
        campaign.planned_end_date = campaign.planned_start_date

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_dates_updated",
            meta_json={
                "campaign_id": campaign.display_id,
                "old_start": old_start.isoformat() if old_start else None,
                "old_end": old_end.isoformat() if old_end else None,
                "new_start": campaign.planned_start_date.isoformat() if campaign.planned_start_date else None,
                "new_end": campaign.planned_end_date.isoformat() if campaign.planned_end_date else None,
            },
        )
    )
    db.commit()
    return {
        "campaign_id": campaign.display_id,
        "planned_start_date": campaign.planned_start_date.isoformat() if campaign.planned_start_date else None,
        "planned_end_date": campaign.planned_end_date.isoformat() if campaign.planned_end_date else None,
    }


@router.get("/campaigns/{campaign_id}/health")
def campaign_health(campaign_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
    deliverable_ids = [d.id for d in deliverables]
    steps = db.scalars(
        select(WorkflowStep).where(
            (WorkflowStep.campaign_id == campaign.id)
            | (WorkflowStep.linked_deliverable_id.in_(deliverable_ids))
        )
    ).all()
    stages = db.scalars(select(Stage).where(Stage.campaign_id == campaign.id).order_by(Stage.name.asc())).all()
    assignments = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    step_ids = [s.id for s in steps]
    efforts: dict[str, list[WorkflowStepEffort]] = {}
    if step_ids:
        for e in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts.setdefault(e.workflow_step_id, []).append(e)
    timeline_health = TimelineHealthService(db)
    campaign_eval, derived_stage = timeline_health.evaluate_campaign(
        campaign=campaign,
        deliverables=deliverables,
        steps=steps,
        efforts_by_step_id=efforts,
        assignments=assignments,
        stages=stages,
    )
    health_service = CampaignHealthService(db)
    health = health_service.evaluate_campaign(campaign)
    return {
        "campaign_id": campaign.display_id,
        "campaign_internal_id": campaign.id,
        "title": campaign.title,
        "type": campaign.campaign_type.value,
        "tier": campaign.tier,
        "overall_status": campaign_eval.health,
        "health_reason": campaign_eval.health_reason,
        "buffer_working_days_remaining": campaign_eval.buffer_working_days_remaining,
        "is_not_due": campaign_eval.is_not_due,
        "derived_stage": derived_stage,
        "worst_signal": health.worst_signal,
        "dimension_scores": health.dimension_scores,
        "next_action": health.next_action,
        "checkpoint_health": health.checkpoint_health,
        "warnings": health.warnings,
    }


@router.get("/deliverables")
def list_deliverables(
    limit: int = 25,
    offset: int = 0,
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    items = db.scalars(select(Deliverable).order_by(Deliverable.created_at.desc())).all()
    campaign_ids = sorted({
        d.campaign_id
        for d in items
        if d.campaign_id
    })
    campaigns_by_id = {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()} if campaign_ids else {}
    owner_ids = sorted({d.owner_user_id for d in items if d.owner_user_id})
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(owner_ids))).all()} if owner_ids else {}
    deliverable_ids = [d.id for d in items]
    open_windows_by_deliverable: dict[str, list[ReviewWindow]] = {}
    if deliverable_ids:
        rows = db.scalars(
            select(ReviewWindow).where(
                ReviewWindow.deliverable_id.in_(deliverable_ids),
                ReviewWindow.status == ReviewWindowStatus.OPEN,
            )
        ).all()
        for row in rows:
            open_windows_by_deliverable.setdefault(row.deliverable_id, []).append(row)
    steps = db.scalars(
        select(WorkflowStep).where(
            WorkflowStep.linked_deliverable_id.in_(deliverable_ids)
        )
    ).all() if deliverable_ids else []
    steps_by_deliverable: dict[str, list[WorkflowStep]] = {}
    for s in steps:
        linked = _step_linked_deliverable(s)
        if linked:
            steps_by_deliverable.setdefault(linked, []).append(s)
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if steps:
        step_ids = [s.id for s in steps]
        for e in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts_by_step.setdefault(e.workflow_step_id, []).append(e)
    timeline_health = TimelineHealthService(db)
    all_items = [
            {
                "id": d.display_id,
                "deliverable_internal_id": d.id,
                "campaign_id": (
                    campaigns_by_id.get(d.campaign_id).display_id
                    if d.campaign_id and campaigns_by_id.get(d.campaign_id)
                    else None
                ),
                "campaign_name": (
                    campaigns_by_id.get(d.campaign_id).title
                    if d.campaign_id and campaigns_by_id.get(d.campaign_id)
                    else None
                ),
                "type": d.deliverable_type.value,
                "module_type": "deliverable",
                "status": _normalize_deliverable_status(d.status).value,
                "delivery_status": d.status.value,
                "health": timeline_health.evaluate_deliverable(
                    deliverable=d,
                    campaign=campaigns_by_id.get(d.campaign_id) if d.campaign_id else None,
                    steps=steps_by_deliverable.get(d.id, []),
                    efforts_by_step_id=efforts_by_step,
                ).health,
                "stage": _deliverable_stage_from_record(d).value,
                "title": d.title,
                "owner_user_id": d.owner_user_id,
                "owner_initials": _initials_for_user_id(d.owner_user_id, users_by_id),
                "current_due": d.current_due.isoformat() if d.current_due else None,
                "current_start": d.current_start.isoformat() if d.current_start else None,
                "awaiting_internal_review_since": (
                    d.awaiting_internal_review_since.isoformat() if d.awaiting_internal_review_since else None
                ),
                "awaiting_client_review_since": (
                    d.awaiting_client_review_since.isoformat() if d.awaiting_client_review_since else None
                ),
                "internal_review_stall_threshold_days": d.internal_review_stall_threshold_days,
                "client_review_stall_threshold_days": d.client_review_stall_threshold_days,
                "ready_to_publish_by_user_id": d.ready_to_publish_by_user_id,
                "internal_review_rounds": d.internal_review_rounds,
                "client_review_rounds": d.client_review_rounds,
                "amend_rounds": d.amend_rounds,
                "review_windows": [
                    {
                        "id": w.display_id,
                        "type": w.window_type.value,
                        "status": w.status.value,
                        "window_start": w.window_start.isoformat(),
                        "window_due": w.window_due.isoformat(),
                        "round_number": w.round_number,
                    }
                    for w in sorted(
                        open_windows_by_deliverable.get(d.id, []),
                        key=lambda x: (x.window_due, x.created_at),
                    )
                ],
            }
            for d in items
    ]
    if status:
        all_items = [i for i in all_items if i["status"] == status]
    if q:
        needle = q.strip().lower()
        all_items = [
            i
            for i in all_items
            if needle in " ".join([i["id"], i["title"], i["type"], i["status"]]).lower()
        ]
    total = len(all_items)
    paged = all_items[offset : offset + limit]
    for i in paged:
        i.pop("deliverable_internal_id", None)
    return {"items": paged, "total": total, "limit": limit, "offset": offset}


@router.get("/reviews/queue")
def reviews_queue(actor_user_id: str, role: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    try:
        role_name = RoleName(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid role") from exc
    if role_name not in actor.roles and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor does not hold selected role")

    windows = db.scalars(select(ReviewWindow).where(ReviewWindow.status == ReviewWindowStatus.OPEN)).all()
    deliverables = {d.id: d for d in db.scalars(select(Deliverable)).all()}
    campaigns = {c.id: c for c in db.scalars(select(Campaign)).all()}
    assignments = db.scalars(select(CampaignAssignment)).all()
    campaign_members: dict[str, set[str]] = {}
    for a in assignments:
        campaign_members.setdefault(a.campaign_id, set()).add(a.user_id)

    grouped = {"awaiting_internal_review": [], "awaiting_client_review": [], "changes_requested": []}
    for w in windows:
        d = deliverables.get(w.deliverable_id)
        if not d:
            continue
        campaign = campaigns.get(d.campaign_id) if d.campaign_id else None
        if campaign and actor_user_id not in campaign_members.get(campaign.id, set()) and RoleName.ADMIN not in actor.roles and RoleName.HEAD_OPS not in actor.roles:
            continue
        item = {
            "window_id": w.display_id,
            "window_type": w.window_type.value,
            "round_number": w.round_number,
            "deliverable_id": d.display_id,
            "deliverable_title": d.title,
            "deliverable_status": d.status.value,
            "campaign_id": campaign.display_id if campaign else None,
            "campaign_title": campaign.title if campaign else None,
            "window_start": w.window_start.isoformat(),
            "window_due": w.window_due.isoformat(),
            "age_days": max((date.today() - w.window_start).days, 0),
        }
        if w.window_type == ReviewWindowType.INTERNAL_REVIEW:
            grouped["awaiting_internal_review"].append(item)
        elif w.window_type == ReviewWindowType.CLIENT_REVIEW:
            grouped["awaiting_client_review"].append(item)
        elif w.window_type == ReviewWindowType.AMENDS:
            grouped["changes_requested"].append(item)

    return {
        "role": role_name.value,
        "summary": {k: len(v) for k, v in grouped.items()},
        "queues": grouped,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/campaigns/{campaign_id}/workspace")
def campaign_workspace(campaign_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    StageIntegrityService(db).reconcile_campaign(campaign.id)
    timeline_health = TimelineHealthService(db)
    scope = db.get(Deal, campaign.deal_id) if campaign.deal_id else None

    deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
    assignment_rows = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    assignments = {row.role_name.value: row.user_id for row in assignment_rows}
    assignment_user_ids = sorted({row.user_id for row in assignment_rows if row.user_id})
    deliverable_ids = [d.id for d in deliverables]
    review_windows = (
        db.scalars(select(ReviewWindow).where(ReviewWindow.deliverable_id.in_(deliverable_ids))).all()
        if deliverable_ids
        else []
    )
    steps = db.scalars(
        select(WorkflowStep).where(
            (WorkflowStep.campaign_id == campaign.id)
            | (WorkflowStep.linked_deliverable_id.in_(deliverable_ids))
        )
    ).all()
    stages = db.scalars(select(Stage).where(Stage.campaign_id == campaign.id).order_by(Stage.name.asc())).all()
    milestones = db.scalars(
        select(Milestone)
        .where(Milestone.campaign_id == campaign.id)
        .order_by(Milestone.current_target_date.asc())
    ).all()
    system_risks = db.scalars(select(SystemRisk).where(SystemRisk.campaign_id == campaign.id, SystemRisk.is_open.is_(True))).all()
    manual_risks = db.scalars(select(ManualRisk).where(ManualRisk.campaign_id == campaign.id, ManualRisk.is_open.is_(True))).all()
    reviews = db.scalars(select(Review).where(Review.deliverable_id.in_(deliverable_ids)).order_by(Review.created_at.desc())).all() if deliverable_ids else []
    step_ids = [s.id for s in steps]
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if step_ids:
        step_efforts = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
        for effort in step_efforts:
            efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
    else:
        step_efforts = []
    user_ids = set(assignment_user_ids).union({
        s.next_owner_user_id
        for s in steps
        if s.next_owner_user_id
    }).union(
        {
            e.assigned_user_id
            for e in step_efforts
            if e.assigned_user_id
        }
    ).union(
        {
            d.owner_user_id
            for d in deliverables
            if d.owner_user_id
        }
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(sorted(user_ids)))).all()} if user_ids else {}
    milestone_start, milestone_due = _campaign_timeframe_from_milestones(milestones)
    timeframe_start = campaign.planned_start_date.isoformat() if campaign.planned_start_date else milestone_start
    timeframe_due = campaign.planned_end_date.isoformat() if campaign.planned_end_date else milestone_due
    activity = db.scalars(
        select(ActivityLog)
        .where(
            ((ActivityLog.entity_type == "deliverable") & (ActivityLog.entity_id.in_(deliverable_ids)))
            | ((ActivityLog.entity_type == "workflow_step") & (ActivityLog.entity_id.in_(step_ids)))
        )
        .order_by(ActivityLog.created_at.desc())
    ).all() if (deliverable_ids or step_ids) else []

    deliverable_status_counts: dict[str, int] = {}
    windows_by_deliverable: dict[str, list[ReviewWindow]] = {}
    for w in review_windows:
        windows_by_deliverable.setdefault(w.deliverable_id, []).append(w)
    for d in deliverables:
        deliverable_status_counts[d.status.value] = deliverable_status_counts.get(d.status.value, 0) + 1

    review_counts = {"pending_internal": 0, "pending_client": 0, "changes_requested": 0}
    for d in deliverables:
        if d.status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            review_counts["pending_internal"] += 1
        if d.status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            review_counts["pending_client"] += 1
        if d.status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
            review_counts["changes_requested"] += 1

    sprint_summary = []
    sprint_label = f"S{campaign.demand_sprint_number}" if campaign.is_demand_sprint and campaign.demand_sprint_number else "Campaign"
    deliverables_by_id = {d.id: d for d in deliverables}
    steps_by_group_label: dict[str, list[WorkflowStep]] = {}
    for st in steps:
        key = sprint_label
        steps_by_group_label.setdefault(key, []).append(st)

    def _phase_for_step(step: WorkflowStep, deliverable: Deliverable | None) -> str:
        if step.stage_name:
            stage = step.stage_name.strip().lower()
            if stage in {"planning", "production", "promotion", "reporting"}:
                return stage
        if step.stage_id:
            stage_rec = next((s for s in stages if s.id == step.stage_id), None)
            if stage_rec and stage_rec.name:
                return str(stage_rec.name).strip().lower()
        linked_deliverable_id = _step_linked_deliverable(step)
        if step.campaign_id and not linked_deliverable_id:
            return "planning"
        if deliverable and deliverable.deliverable_type.value in {"report", "engagement_list", "lead_total"}:
            return "reporting"
        if deliverable and deliverable.deliverable_type.value == "display_asset":
            return "promotion"
        return "production"

    grouping_keys = sorted(steps_by_group_label.keys()) or [sprint_label]
    for key in grouping_keys:
        s_deliverables = [
            d for d in deliverables
            if (d.campaign_id == campaign.id and key == sprint_label)
        ]
        sections: dict[str, list[dict]] = {"planning": [], "production": [], "promotion": [], "reporting": []}
        for st in sorted(
            steps_by_group_label.get(key, []),
            key=lambda x: (
                x.current_due or date.max,
                x.created_at.date(),
            ),
        ):
            linked_deliverable_id = _step_linked_deliverable(st)
            parent_deliverable = deliverables_by_id.get(linked_deliverable_id) if linked_deliverable_id else None
            phase = _phase_for_step(st, parent_deliverable)
            sections[phase].append(
                {
                    "id": st.display_id,
                    "name": st.name,
                    "module_type": _step_module_type(st),
                    "step_kind": st.step_kind.value,
                    "status": _normalize_step_status(st).value,
                    "health": timeline_health.evaluate_step(st, campaign=campaign).health,
                    "owner_role": st.owner_role.value,
                    "next_owner_user_id": st.next_owner_user_id,
                    "owner_initials": _initials_for_user_id(st.next_owner_user_id, users_by_id),
                    "participant_initials": _participant_initials_for_step(st, efforts_by_step, users_by_id),
                    "current_start": st.current_start.isoformat() if st.current_start else None,
                    "current_due": st.current_due.isoformat() if st.current_due else None,
                    "waiting_on_type": st.waiting_on_type.value if st.waiting_on_type else None,
                    "blocker_reason": st.blocker_reason,
                    "deliverable_id": parent_deliverable.display_id if parent_deliverable else None,
                    "deliverable_title": parent_deliverable.title if parent_deliverable else None,
                    "linked_deliverable_id": parent_deliverable.display_id if parent_deliverable else None,
                    "linked_deliverable_title": parent_deliverable.title if parent_deliverable else None,
                    "stage_id": st.stage_id,
                    "effort_allocations": [
                        {
                            "role": e.role_name.value,
                            "hours": float(e.hours),
                            "assigned_user_id": e.assigned_user_id,
                        }
                        for e in sorted(efforts_by_step.get(st.id, []), key=lambda x: (x.role_name.value, x.created_at))
                    ],
                }
            )
        sections = {k: v for k, v in sections.items() if v}
        sprint_summary.append(
            {
                "id": key,
                "sprint_number": campaign.demand_sprint_number if campaign.is_demand_sprint else 1,
                "baseline_start": None,
                "current_start": None,
                "deliverables_total": len(s_deliverables),
                "deliverables_complete": len([d for d in s_deliverables if d.status == DeliverableStatus.COMPLETE]),
                "sections": sections,
            }
        )

    health_service = CampaignHealthService(db)
    health = health_service.evaluate_campaign(campaign)
    campaign_health_eval, derived_stage = timeline_health.evaluate_campaign(
        campaign=campaign,
        deliverables=deliverables,
        steps=steps,
        efforts_by_step_id=efforts_by_step,
        assignments=assignment_rows,
        stages=stages,
    )

    return {
        "campaign": {
            "id": campaign.display_id,
            "scope_id": scope.display_id if scope else None,
            "title": campaign.title,
            "type": campaign.campaign_type.value,
            "tier": campaign.tier,
            "status": _normalize_campaign_status(campaign.status).value,
            "module_type": "campaign",
            "health": campaign_health_eval.health,
            "health_reason": campaign_health_eval.health_reason,
            "buffer_working_days_remaining": campaign_health_eval.buffer_working_days_remaining,
            "is_not_due": campaign_health_eval.is_not_due,
            "timeframe_start": timeframe_start,
            "timeframe_due": timeframe_due,
            "campaign_name": campaign.title,
            "campaign_status": _normalize_campaign_status(campaign.status).value,
            "campaign_health": campaign_health_eval.health,
            "derived_stage": derived_stage,
            "is_demand_sprint": campaign.is_demand_sprint,
            "demand_sprint_number": campaign.demand_sprint_number,
            "demand_track": campaign.demand_track,
            "sprint_label": (f"S{campaign.demand_sprint_number}" if campaign.is_demand_sprint and campaign.demand_sprint_number else None),
            "assignments": assignments,
            "assigned_users": [
                {
                    "user_id": row.user_id,
                    "role": row.role_name.value,
                    "name": users_by_id.get(row.user_id).full_name if users_by_id.get(row.user_id) else None,
                    "initials": _initials_for_user_id(row.user_id, users_by_id),
                }
                for row in sorted(assignment_rows, key=lambda x: x.role_name.value)
            ],
            "assigned_user_initials": [
                _initials_for_user_id(row.user_id, users_by_id)
                for row in sorted(assignment_rows, key=lambda x: x.role_name.value)
                if row.user_id
            ],
        },
        "health_summary": {
            "overall_status": campaign_health_eval.health,
            "health_reason": campaign_health_eval.health_reason,
            "buffer_working_days_remaining": campaign_health_eval.buffer_working_days_remaining,
            "is_not_due": campaign_health_eval.is_not_due,
            "worst_signal": health.worst_signal,
            "dimension_scores": health.dimension_scores,
            "checkpoint_health": health.checkpoint_health,
            "warnings": health.warnings,
        },
        "next_action": health.next_action,
        "overview": {
            "sprints_total": max(len(sprint_summary), 1),
            "deliverables_total": len(deliverables),
            "workflow_steps_open": len([s for s in steps if s.actual_done is None]),
            "open_system_risks": len(system_risks),
            "open_manual_risks": len(manual_risks),
        },
        "sprints": sprint_summary,
        "deliverables": {
            "counts_by_status": deliverable_status_counts,
            "items": [
                {
                    "id": d.display_id,
                    "title": d.title,
                    "module_type": "deliverable",
                    "type": d.deliverable_type.value,
                    "status": _normalize_deliverable_status(d.status).value,
                    "delivery_status": d.status.value,
                    "health": timeline_health.evaluate_deliverable(
                        deliverable=d,
                        campaign=campaign,
                        steps=[s for s in steps if _step_linked_deliverable(s) == d.id],
                        efforts_by_step_id=efforts_by_step,
                    ).health,
                    "stage": _deliverable_stage_from_record(d).value,
                    "owner_user_id": d.owner_user_id,
                    "owner_initials": _initials_for_user_id(d.owner_user_id, users_by_id),
                    "current_due": d.current_due.isoformat() if d.current_due else None,
                    "current_start": d.current_start.isoformat() if d.current_start else None,
                    "internal_review_rounds": d.internal_review_rounds,
                    "client_review_rounds": d.client_review_rounds,
                    "amend_rounds": d.amend_rounds,
                    "review_windows": [
                        {
                            "id": w.display_id,
                            "type": w.window_type.value,
                            "status": w.status.value,
                            "window_start": w.window_start.isoformat(),
                            "window_due": w.window_due.isoformat(),
                            "round_number": w.round_number,
                        }
                        for w in sorted(windows_by_deliverable.get(d.id, []), key=lambda x: (x.window_start, x.created_at))
                    ],
                }
                for d in deliverables
            ],
        },
        "workflow_steps": {
            "items": [
                {
                    "id": s.display_id,
                    "name": s.name,
                    "module_type": _step_module_type(s),
                    "step_kind": s.step_kind.value,
                    "status": _normalize_step_status(s).value,
                    "health": timeline_health.evaluate_step(s, campaign=campaign).health,
                    "owner_role": s.owner_role.value,
                    "current_due": s.current_due.isoformat() if s.current_due else None,
                    "next_owner_user_id": s.next_owner_user_id,
                    "owner_initials": _initials_for_user_id(s.next_owner_user_id, users_by_id),
                    "participant_initials": _participant_initials_for_step(s, efforts_by_step, users_by_id),
                    "current_start": s.current_start.isoformat() if s.current_start else None,
                    "waiting_on_type": s.waiting_on_type.value if s.waiting_on_type else None,
                    "blocker_reason": s.blocker_reason,
                    "step_state": (
                        _normalize_step_status(s).value
                    ),
                    "stage_name": s.stage_name,
                    "stage_id": s.stage_id,
                    "effort_allocations": [
                        {
                            "role": e.role_name.value,
                            "hours": float(e.hours),
                            "assigned_user_id": e.assigned_user_id,
                        }
                        for e in sorted(efforts_by_step.get(s.id, []), key=lambda x: (x.role_name.value, x.created_at))
                    ],
                    "campaign_id": campaign.display_id,
                    "parent_type": "stage" if s.stage_id else "campaign",
                    "deliverable_id": deliverables_by_id.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                    "deliverable_title": deliverables_by_id.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                    "linked_deliverable_id": deliverables_by_id.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                    "linked_deliverable_title": deliverables_by_id.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                }
                for s in steps
            ]
        },
        "stages": [
            {
                "id": st.id,
                "display_id": st.display_id,
                "name": st.name,
                "status": str(st.status.value if hasattr(st.status, "value") else st.status),
                "health": str(st.health.value if hasattr(st.health, "value") else st.health),
                "baseline_start": st.baseline_start.isoformat() if st.baseline_start else None,
                "baseline_due": st.baseline_due.isoformat() if st.baseline_due else None,
                "current_start": st.current_start.isoformat() if st.current_start else None,
                "current_due": st.current_due.isoformat() if st.current_due else None,
                "actual_done": st.actual_done.isoformat() if st.actual_done else None,
                "step_count": len([x for x in steps if x.stage_id == st.id]),
            }
            for st in stages
        ],
        "reviews": {
            "counts": review_counts,
            "recent": [
                {
                    "id": r.display_id,
                    "review_type": r.review_type,
                    "status": r.status,
                    "comments": r.comments,
                    "created_at": r.created_at.isoformat(),
                }
                for r in reviews[:20]
            ],
        },
        "risks": {
            "system": [
                {"id": r.display_id, "severity": r.severity.value, "code": r.risk_code, "details": r.details}
                for r in system_risks
            ],
            "manual": [
                {"id": r.display_id, "severity": r.severity.value, "details": r.details}
                for r in manual_risks
            ],
        },
        "timeline": {
            "milestones": [
                {
                    "id": m.display_id,
                    "name": m.name,
                    "baseline_date": m.baseline_date.isoformat() if m.baseline_date else None,
                    "current_target_date": m.current_target_date.isoformat() if m.current_target_date else None,
                    "achieved_at": m.achieved_at.isoformat() if m.achieved_at else None,
                }
                for m in milestones[:50]
            ],
        },
        "activity": [
            {
                "id": a.display_id,
                "action": a.action,
                "created_at": a.created_at.isoformat(),
                "meta": a.meta_json,
            }
            for a in activity[:30]
        ],
    }


@router.post("/deliverables/{deliverable_id}/transition")
def transition_deliverable(deliverable_id: str, payload: DeliverableTransitionIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    campaign = _campaign_for_deliverable(db, deliverable)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_campaign_member_or_roles(
        actor=actor,
        campaign=campaign,
        member_roles={RoleName.AM, RoleName.CM, RoleName.CC, RoleName.CCS},
        fallback_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    )

    try:
        to_status = DeliverableStatus(payload.to_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid to_status") from exc

    updated = DeliverableWorkflowService(db).transition(
        deliverable=deliverable,
        to_status=to_status,
        actor_user_id=payload.actor_user_id,
        actor_roles=actor.roles,
        comment=payload.comment,
    )
    db.commit()
    health_payload = _evaluate_deliverable_health(db, updated)
    return {
        "id": updated.display_id,
        "status": _normalize_deliverable_status(updated.status).value,
        "delivery_status": updated.status.value,
        "health": health_payload["health"],
        "health_reason": health_payload["health_reason"],
        "buffer_working_days_remaining": health_payload["buffer_working_days_remaining"],
        "is_not_due": health_payload["is_not_due"],
        "stage": _deliverable_stage_from_record(updated).value,
        "ready_to_publish_at": updated.ready_to_publish_at,
        "actual_done": updated.actual_done,
    }


@router.delete("/deliverables/{deliverable_id}")
def delete_deliverable(deliverable_id: str, actor_user_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "delete_deliverable",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="not permitted to delete deliverable")

    deleted = _delete_deliverable_graph(db, deliverable.id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_deleted",
            meta_json={"deliverable_id": deliverable.display_id, "deleted_counts": deleted},
        )
    )
    db.commit()
    return {"deleted": True, "deliverable_id": deliverable.display_id, "counts": deleted}


@router.post("/deliverables/{deliverable_id}/override-due")
def override_deliverable_due(deliverable_id: str, payload: DeliverableDueUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "override_step_due",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit due dates")

    try:
        requested = date.fromisoformat(payload.current_due_iso)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid current_due_iso; expected YYYY-MM-DD") from exc

    calendar = build_default_working_calendar()
    adjusted_due = calendar.next_working_day_on_or_after(requested)
    old_due = deliverable.current_due
    deliverable.current_due = adjusted_due
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_due_overridden",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_due": old_due.isoformat() if old_due else None,
                "new_due": adjusted_due.isoformat(),
                "reason_code": payload.reason_code,
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "current_due": adjusted_due.isoformat(),
        "reason_code": payload.reason_code,
    }


@router.patch("/deliverables/{deliverable_id}/dates")
def update_deliverable_dates(deliverable_id: str, payload: DeliverableDatesUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_deliverable_dates",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit deliverable dates")
    if not payload.current_start_iso and not payload.current_due_iso:
        raise HTTPException(status_code=400, detail="at least one date is required")

    calendar = build_default_working_calendar()
    old_start = deliverable.current_start
    old_due = deliverable.current_due

    if payload.current_start_iso:
        try:
            requested_start = date.fromisoformat(payload.current_start_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid current_start_iso; expected YYYY-MM-DD") from exc
        deliverable.current_start = calendar.next_working_day_on_or_after(requested_start)

    if payload.current_due_iso:
        try:
            requested_due = date.fromisoformat(payload.current_due_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid current_due_iso; expected YYYY-MM-DD") from exc
        deliverable.current_due = calendar.next_working_day_on_or_after(requested_due)

    if deliverable.current_start and deliverable.current_due and deliverable.current_due < deliverable.current_start:
        deliverable.current_due = deliverable.current_start

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_dates_updated",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_start": old_start.isoformat() if old_start else None,
                "old_due": old_due.isoformat() if old_due else None,
                "new_start": deliverable.current_start.isoformat() if deliverable.current_start else None,
                "new_due": deliverable.current_due.isoformat() if deliverable.current_due else None,
                "reason_code": payload.reason_code or "schedule_adjustment",
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "current_start": deliverable.current_start.isoformat() if deliverable.current_start else None,
        "current_due": deliverable.current_due.isoformat() if deliverable.current_due else None,
        "reason_code": payload.reason_code or "schedule_adjustment",
    }


@router.patch("/deliverables/{deliverable_id}/stage")
def update_deliverable_stage(deliverable_id: str, payload: DeliverableStageUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "edit_deliverable_stage",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit deliverable stage")

    try:
        new_stage = DeliverableStage(payload.stage.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid stage") from exc

    old_stage = _deliverable_stage_from_record(deliverable).value
    deliverable.stage = new_stage
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_stage_updated",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_stage": old_stage,
                "new_stage": new_stage.value,
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "stage": new_stage.value,
    }


@router.patch("/deliverables/{deliverable_id}/owner")
def update_deliverable_owner(deliverable_id: str, payload: DeliverableOwnerUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_deliverable_owner",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit deliverable owner")

    old_owner = deliverable.owner_user_id
    new_owner = payload.owner_user_id or None
    if new_owner:
        u = db.get(User, new_owner)
        if not u:
            raise HTTPException(status_code=400, detail="owner_user_id not found")
    deliverable.owner_user_id = new_owner

    users_by_id: dict[str, User] = {}
    if deliverable.owner_user_id:
        owner = db.get(User, deliverable.owner_user_id)
        if owner:
            users_by_id[owner.id] = owner
    owner_initials = _initials_for_user_id(deliverable.owner_user_id, users_by_id)

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_owner_updated",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_owner_user_id": old_owner,
                "new_owner_user_id": deliverable.owner_user_id,
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "owner_user_id": deliverable.owner_user_id,
        "owner_initials": owner_initials,
    }


@router.get("/deliverables/{deliverable_id}/history")
def deliverable_history(deliverable_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    activity = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.entity_type == "deliverable", ActivityLog.entity_id == deliverable.id)
        .order_by(ActivityLog.created_at.desc())
    ).all()
    reviews = db.scalars(
        select(Review)
        .where(Review.deliverable_id == deliverable.id)
        .order_by(Review.created_at.desc())
    ).all()

    return {
        "deliverable": {
            "id": deliverable.display_id,
            "title": deliverable.title,
            "status": _normalize_deliverable_status(deliverable.status).value,
            "delivery_status": deliverable.status.value,
            "health": _evaluate_deliverable_health(db, deliverable)["health"],
            "stage": _deliverable_stage_from_record(deliverable).value,
            "internal_review_rounds": deliverable.internal_review_rounds,
            "client_review_rounds": deliverable.client_review_rounds,
            "amend_rounds": deliverable.amend_rounds,
            "awaiting_internal_review_since": (
                deliverable.awaiting_internal_review_since.isoformat() if deliverable.awaiting_internal_review_since else None
            ),
            "awaiting_client_review_since": (
                deliverable.awaiting_client_review_since.isoformat() if deliverable.awaiting_client_review_since else None
            ),
            "internal_review_stall_threshold_days": deliverable.internal_review_stall_threshold_days,
            "client_review_stall_threshold_days": deliverable.client_review_stall_threshold_days,
        },
        "activity": [
            {
                "id": a.display_id,
                "action": a.action,
                "created_at": a.created_at.isoformat(),
                "meta": a.meta_json,
            }
            for a in activity
        ],
        "reviews": [
            {
                "id": r.display_id,
                "review_type": r.review_type,
                "status": r.status,
                "comments": r.comments,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }


@router.get("/deliverables/{deliverable_id}/review-windows")
def deliverable_review_windows(deliverable_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")
    windows = DeliverableWorkflowService(db).list_windows(deliverable)
    round_events = db.scalars(
        select(ReviewRoundEvent)
        .where(ReviewRoundEvent.deliverable_id == deliverable.id)
        .order_by(ReviewRoundEvent.event_at.desc(), ReviewRoundEvent.created_at.desc())
    ).all()
    return {
        "deliverable": {
            "id": deliverable.display_id,
            "title": deliverable.title,
            "status": _normalize_deliverable_status(deliverable.status).value,
            "delivery_status": deliverable.status.value,
            "health": _evaluate_deliverable_health(db, deliverable)["health"],
            "stage": _deliverable_stage_from_record(deliverable).value,
            "internal_review_rounds": deliverable.internal_review_rounds,
            "client_review_rounds": deliverable.client_review_rounds,
            "amend_rounds": deliverable.amend_rounds,
        },
        "windows": [
            {
                "id": w.display_id,
                "type": w.window_type.value,
                "status": w.status.value,
                "window_start": w.window_start.isoformat(),
                "window_due": w.window_due.isoformat(),
                "completed_at": w.completed_at.isoformat() if w.completed_at else None,
                "round_number": w.round_number,
            }
            for w in windows
        ],
        "round_events": [
            {
                "id": e.display_id,
                "event_type": e.event_type.value,
                "round_number": e.round_number,
                "event_at": e.event_at.isoformat(),
                "actor_user_id": e.actor_user_id,
                "note": e.note,
                "source": e.source,
            }
            for e in round_events
        ],
    }


@router.post("/deliverables/{deliverable_id}/review-rounds/increment")
def increment_review_round(deliverable_id: str, payload: ReviewRoundIncrementIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.AM, RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN})
    result = DeliverableWorkflowService(db).increment_round(
        deliverable=deliverable,
        round_type=payload.round_type,
        actor_user_id=payload.actor_user_id,
        note=payload.note,
    )
    db.commit()
    return result


@router.get("/workflow-steps")
def list_workflow_steps(db: Session = Depends(get_db)):
    items = db.scalars(select(WorkflowStep).order_by(WorkflowStep.created_at.asc())).all()
    step_ids = [s.id for s in items]
    efforts = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all() if step_ids else []
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    for effort in efforts:
        efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
    deliverable_ids = {_step_linked_deliverable(s) for s in items if _step_linked_deliverable(s)}
    deliverables = (
        {d.id: d for d in db.scalars(select(Deliverable).where(Deliverable.id.in_(deliverable_ids))).all()}
        if deliverable_ids
        else {}
    )
    campaign_ids = {d.campaign_id for d in deliverables.values() if d.campaign_id}.union({s.campaign_id for s in items if s.campaign_id})
    campaigns = {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()} if campaign_ids else {}
    owner_ids = {s.next_owner_user_id for s in items if s.next_owner_user_id}
    participant_ids = {e.assigned_user_id for e in efforts if e.assigned_user_id}
    user_ids = sorted(owner_ids.union(participant_ids))
    owners = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    timeline_health = TimelineHealthService(db)

    def _step_state(step: WorkflowStep) -> str:
        if step.actual_done:
            return "done"
        if step.waiting_on_type:
            return f"blocked_{step.waiting_on_type.value}"
        if step.actual_start:
            return "in_progress"
        return "not_started"

    return {
        "items": [
            {
                "id": s.display_id,
                "name": s.name,
                "module_type": _step_module_type(s),
                "step_kind": s.step_kind.value,
                "owner_role": s.owner_role.value,
                "status": _normalize_step_status(s).value,
                "health": timeline_health.evaluate_step(
                    s,
                    campaign=(
                        campaigns.get(s.campaign_id)
                        or (
                            campaigns.get(deliverables.get(_step_linked_deliverable(s)).campaign_id)
                            if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) and deliverables.get(_step_linked_deliverable(s)).campaign_id
                            else None
                        )
                    ),
                ).health,
                "step_state": _step_state(s),
                "current_start": s.current_start.isoformat() if s.current_start else None,
                "current_due": s.current_due.isoformat() if s.current_due else None,
                "actual_done": s.actual_done.isoformat() if s.actual_done else None,
                "parent_type": "stage" if s.stage_id else "campaign",
                "next_owner_user_id": s.next_owner_user_id,
                "next_owner_name": owners.get(s.next_owner_user_id).full_name if owners.get(s.next_owner_user_id) else None,
                "owner_initials": _initials_for_user_id(s.next_owner_user_id, owners),
                "participant_initials": _participant_initials_for_step(s, efforts_by_step, owners),
                "waiting_on_type": s.waiting_on_type.value if s.waiting_on_type else None,
                "waiting_on_user_id": s.waiting_on_user_id,
                "blocker_reason": s.blocker_reason,
                "deliverable_id": deliverables.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "deliverable_title": deliverables.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "linked_deliverable_id": deliverables.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "linked_deliverable_title": deliverables.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "campaign_id": (
                    campaigns.get(s.campaign_id).display_id
                    if s.campaign_id and campaigns.get(s.campaign_id)
                    else (
                        campaigns.get(deliverables.get(_step_linked_deliverable(s)).campaign_id).display_id
                        if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) and deliverables.get(_step_linked_deliverable(s)).campaign_id and campaigns.get(deliverables.get(_step_linked_deliverable(s)).campaign_id)
                        else None
                    )
                ),
                "stage_name": s.stage_name,
                "stage_id": s.stage_id,
                "effort_allocations": [
                    {
                        "role": e.role_name.value,
                        "hours": float(e.hours),
                        "assigned_user_id": e.assigned_user_id,
                    }
                    for e in sorted(efforts_by_step.get(s.id, []), key=lambda x: (x.role_name.value, x.created_at))
                ],
            }
            for s in items
        ]
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name.asc())).all()
    user_ids = [u.id for u in users]
    assignments = db.scalars(select(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(user_ids))).all() if user_ids else []
    role_ids = sorted({a.role_id for a in assignments})
    roles = {r.id: r for r in db.scalars(select(Role).where(Role.id.in_(role_ids))).all()} if role_ids else {}
    roles_map: dict[str, list[str]] = {u.id: [] for u in users}
    for a in assignments:
        role = roles.get(a.role_id)
        if role:
            roles_map.setdefault(a.user_id, []).append(role.name.value)
    return {
        "items": [
            {
                "id": u.id,
                "name": u.full_name,
                "email": u.email,
                "roles": sorted(set(roles_map.get(u.id, []))),
                "primary_team": u.primary_team.value,
                "seniority": u.seniority.value,
                "app_role": u.app_role.value,
            }
            for u in users
        ]
    }


@router.get("/milestones")
def list_milestones(db: Session = Depends(get_db)):
    items = db.scalars(select(Milestone).order_by(Milestone.created_at.asc())).all()
    return {
        "items": [
            {
                "id": m.display_id,
                "campaign_id": m.campaign_id,
                "name": m.name,
                "baseline_date": m.baseline_date.isoformat() if m.baseline_date else None,
                "current_target_date": m.current_target_date.isoformat() if m.current_target_date else None,
                "achieved_at": m.achieved_at.isoformat() if m.achieved_at else None,
            }
            for m in items
        ]
    }


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    deals = db.scalars(select(Deal)).all()
    campaigns = db.scalars(select(Campaign)).all()
    deliverables = db.scalars(select(Deliverable)).all()
    steps = db.scalars(select(WorkflowStep)).all()

    at_risk_steps = [
        s
        for s in steps
        if s.current_due is not None and s.actual_done is None
    ]

    awaiting_client_review = [
        d for d in deliverables if d.status == DeliverableStatus.AWAITING_CLIENT_REVIEW
    ]
    waiting_publish = [
        d for d in deliverables if d.status == DeliverableStatus.READY_TO_PUBLISH
    ]
    open_system_risks = db.scalars(select(SystemRisk).where(SystemRisk.is_open.is_(True))).all()
    open_manual_risks = db.scalars(select(ManualRisk).where(ManualRisk.is_open.is_(True))).all()
    over_capacity_rows = db.scalars(
        select(CapacityLedger).where(CapacityLedger.planned_hours > CapacityLedger.capacity_hours)
    ).all()
    open_escalations = db.scalars(select(Escalation).where(Escalation.resolved_at.is_(None))).all()

    return {
        "deals_total": len(deals),
        "deals_readiness_passed": len([d for d in deals if d.readiness_passed]),
        "campaigns_total": len(campaigns),
        "deliverables_total": len(deliverables),
        "workflow_steps_open": len([s for s in steps if s.actual_done is None]),
        "workflow_steps_due_tracked": len(at_risk_steps),
        "awaiting_client_review": len(awaiting_client_review),
        "ready_to_publish": len(waiting_publish),
        "open_system_risks": len(open_system_risks),
        "open_manual_risks": len(open_manual_risks),
        "over_capacity_rows": len(over_capacity_rows),
        "open_escalations": len(open_escalations),
    }


@router.get("/dashboard/role")
def dashboard_by_role(role: str, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)

    try:
        role_name = RoleName(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid role") from exc

    if role_name not in actor.roles and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor does not hold selected role")

    summary = dashboard_summary(db)
    my_work = MyWorkQueueService(db).build(actor_user_id)

    identity_permissions = _identity_permissions_payload(db)
    screen_rules = identity_permissions.get("screen_flags") or {}
    campaign_control_rules = identity_permissions.get("campaign_control_permissions") or {}
    app_control_rules = identity_permissions.get("app_control_permissions") or {}
    legacy_control_rules = identity_permissions.get("control_permissions") or {}
    role_flags = {
        key: _identity_rule_allows(
            screen_rules.get(key),
            team=actor.primary_team,
            seniority=actor.seniority,
            app_role=actor.app_role,
        )
        for key in ("show_deals_pipeline", "show_capacity", "show_risks", "show_reviews", "show_admin")
    }
    controls: set[str] = set()
    for control_id, rule in campaign_control_rules.items():
        if _identity_campaign_rule_allows(
            rule,
            team=actor.primary_team,
            seniority=actor.seniority,
            app_role=actor.app_role,
        ):
            controls.add(control_id)
    for control_id, rule in app_control_rules.items():
        if _identity_app_rule_allows(
            rule,
            seniority=actor.seniority,
            app_role=actor.app_role,
        ):
            controls.add(control_id)
    for control_id, rule in legacy_control_rules.items():
        if _identity_rule_allows(
            rule,
            team=actor.primary_team,
            seniority=actor.seniority,
            app_role=actor.app_role,
        ):
            controls.add(control_id)
    return {
        "role": role_name.value,
        "summary": summary,
        "my_queue_count": my_work["summary"]["total"],
        "my_work_summary": my_work["summary"],
        "flags": role_flags,
        "controls": sorted(controls),
        "identity": {
            "team": actor.primary_team.value,
            "seniority": actor.seniority.value,
            "app_role": actor.app_role.value,
        },
    }


@router.get("/admin/ops-defaults")
def get_ops_defaults(actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})
    payload = OpsDefaultsService(db).get()
    return {"defaults": payload}


@router.put("/admin/ops-defaults")
def update_ops_defaults(payload: OpsDefaultsUpdateIn, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})
    try:
        updated = OpsDefaultsService(db).upsert(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="ops_default_configs",
            entity_id=OpsDefaultsService.CONFIG_KEY,
            action="ops_defaults_updated",
            meta_json={"keys": list(payload.model_dump(exclude_none=True).keys())},
        )
    )
    db.commit()
    return {"defaults": updated}


@router.get("/admin/role-permissions")
def get_role_permissions(actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})
    payload = _role_permissions_payload(db)
    identity = _identity_permissions_payload(db)
    return {
        "role_permissions": payload,
        "identity_permissions": identity,
        "roles": [r.value for r in RoleName],
        "teams": [t.value for t in TeamName],
        "seniorities": [s.value for s in SeniorityLevel],
        "app_roles": [a.value for a in AppAccessRole],
        "editable_roles": ["am", "head_ops", "cm", "cc", "dn", "mm", "admin", "leadership_viewer", "head_sales", "client"],
    }


@router.put("/admin/role-permissions")
def update_role_permissions(payload: RolePermissionsUpdateIn, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})

    patch: dict[str, Any] = {"role_permissions": {"role_flags": payload.role_flags, "control_permissions": payload.control_permissions}}
    if payload.identity_permissions:
        patch["identity_permissions"] = payload.identity_permissions
    updated = OpsDefaultsService(db).upsert(patch)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="ops_default_configs",
            entity_id=OpsDefaultsService.CONFIG_KEY,
            action="role_permissions_updated",
            meta_json={"roles_updated": sorted((payload.role_flags or {}).keys())},
        )
    )
    db.commit()
    role_permissions = (updated.get("role_permissions") or {})
    identity_permissions = (updated.get("identity_permissions") or {})
    return {"role_permissions": role_permissions, "identity_permissions": identity_permissions}


@router.get("/admin/users")
def admin_list_users(actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})

    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name.asc())).all()
    user_ids = [u.id for u in users]
    assignments = db.scalars(select(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(user_ids))).all() if user_ids else []
    role_ids = sorted({a.role_id for a in assignments})
    roles = {r.id: r for r in db.scalars(select(Role).where(Role.id.in_(role_ids))).all()} if role_ids else {}
    roles_map: dict[str, list[str]] = {u.id: [] for u in users}
    for a in assignments:
        role = roles.get(a.role_id)
        if role:
            roles_map.setdefault(a.user_id, []).append(role.name.value)
    editable_roles = [r.value for r in RoleName if r != RoleName.CCS]
    return {
        "items": [
            {
                "id": u.id,
                "name": u.full_name,
                "email": u.email,
                "is_active": bool(u.is_active),
                "roles": sorted(set(roles_map.get(u.id, []))),
                "primary_team": u.primary_team.value,
                "seniority": u.seniority.value,
                "app_role": u.app_role.value,
            }
            for u in users
        ],
        "editable_roles": editable_roles,
        "teams": [t.value for t in TeamName],
        "seniorities": [s.value for s in SeniorityLevel],
        "app_roles": [a.value for a in AppAccessRole],
    }


@router.post("/admin/users")
def admin_create_user(payload: AdminUserCreateIn, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "admin_add_user",
        fallback_allowed_roles={RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    full_name = str(payload.full_name or "").strip()
    email = str(payload.email or "").strip().lower()
    if not full_name:
        raise HTTPException(status_code=400, detail="full_name is required")
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="email already exists")

    try:
        primary_team = TeamName(str(payload.primary_team or "").strip().lower())
        seniority = SeniorityLevel(str(payload.seniority or "").strip().lower())
        app_role = AppAccessRole(str(payload.app_role or "").strip().lower())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid primary_team/seniority/app_role") from exc

    if not _actor_has_control_permission(
        db, actor, "admin_set_user_team", fallback_allowed_roles={RoleName.ADMIN}
    ):
        raise HTTPException(status_code=403, detail="cannot set user team")
    if seniority == SeniorityLevel.LEADERSHIP:
        if not _actor_has_control_permission(
            db, actor, "admin_set_user_seniority_leadership"
        ):
            raise HTTPException(status_code=403, detail="cannot set leadership seniority")
    else:
        if not _actor_has_control_permission(
            db, actor, "admin_set_user_seniority_manager", fallback_allowed_roles={RoleName.ADMIN}
        ):
            raise HTTPException(status_code=403, detail="cannot set user seniority")

    if app_role == AppAccessRole.SUPERADMIN:
        if not _actor_has_control_permission(db, actor, "admin_set_user_app_role_superadmin"):
            raise HTTPException(status_code=403, detail="cannot set superadmin app role")
    elif app_role == AppAccessRole.ADMIN:
        if not _actor_has_control_permission(db, actor, "admin_set_user_app_role_admin"):
            raise HTTPException(status_code=403, detail="cannot set admin app role")
    elif app_role != AppAccessRole.USER:
        raise HTTPException(status_code=400, detail="invalid app_role")
    requested_roles = sorted(_legacy_roles_for_identity(primary_team, seniority, app_role), key=lambda r: r.value)

    role_rows = db.scalars(select(Role).where(Role.name.in_(requested_roles))).all()
    role_by_name = {r.name: r for r in role_rows}
    missing = [r.value for r in requested_roles if r not in role_by_name]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing role records: {', '.join(sorted(set(missing)))}")

    user = User(
        email=email,
        full_name=full_name,
        is_active=True,
        primary_team=primary_team,
        seniority=seniority,
        app_role=app_role,
    )
    db.add(user)
    db.flush()

    seen = set()
    for role_name in requested_roles:
        if role_name in seen:
            continue
        seen.add(role_name)
        db.add(UserRoleAssignment(user_id=user.id, role_id=role_by_name[role_name].id))

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="user",
            entity_id=user.id,
            action="user_created",
            meta_json={"email": email, "roles": sorted([r.value for r in seen])},
        )
    )
    db.commit()
    db.refresh(user)
    return {
        "item": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "is_active": bool(user.is_active),
                "roles": sorted([r.value for r in seen]),
                "primary_team": user.primary_team.value,
                "seniority": user.seniority.value,
                "app_role": user.app_role.value,
            }
        }


@router.put("/admin/users/{user_id}/roles")
def admin_update_user_roles(user_id: str, payload: AdminUserRolesUpdateIn, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.ADMIN, RoleName.HEAD_OPS})

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    try:
        primary_team = TeamName(str(payload.primary_team or "").strip().lower())
        seniority = SeniorityLevel(str(payload.seniority or "").strip().lower())
        app_role = AppAccessRole(str(payload.app_role or "").strip().lower())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid primary_team/seniority/app_role") from exc

    updates_meta: dict[str, Any] = {}
    new_full_name = str(payload.full_name or "").strip()
    if payload.full_name is not None and new_full_name and new_full_name != user.full_name:
        if not _actor_has_control_permission(
            db, actor, "admin_edit_user_name", fallback_allowed_roles={RoleName.ADMIN}
        ):
            raise HTTPException(status_code=403, detail="cannot edit user name")
        user.full_name = new_full_name
        updates_meta["full_name"] = new_full_name

    if payload.email is not None:
        new_email = str(payload.email or "").strip().lower()
        if not new_email:
            raise HTTPException(status_code=400, detail="email cannot be empty")
        if new_email != user.email.lower():
            if not _actor_has_control_permission(
                db, actor, "admin_edit_user_email", fallback_allowed_roles={RoleName.ADMIN}
            ):
                raise HTTPException(status_code=403, detail="cannot edit user email")
            existing_email_user = db.scalar(select(User).where(func.lower(User.email) == new_email, User.id != user.id))
            if existing_email_user:
                raise HTTPException(status_code=409, detail="email already exists")
            user.email = new_email
            updates_meta["email"] = new_email

    if not _actor_has_control_permission(
        db, actor, "admin_set_user_team", fallback_allowed_roles={RoleName.ADMIN}
    ):
        raise HTTPException(status_code=403, detail="cannot set user team")
    user.primary_team = primary_team

    if seniority == SeniorityLevel.LEADERSHIP:
        if not _actor_has_control_permission(db, actor, "admin_set_user_seniority_leadership"):
            raise HTTPException(status_code=403, detail="cannot set leadership seniority")
    else:
        if not _actor_has_control_permission(
            db, actor, "admin_set_user_seniority_manager", fallback_allowed_roles={RoleName.ADMIN}
        ):
            raise HTTPException(status_code=403, detail="cannot set user seniority")
    user.seniority = seniority

    if app_role != user.app_role:
        if app_role == AppAccessRole.SUPERADMIN:
            if not _actor_has_control_permission(db, actor, "admin_set_user_app_role_superadmin"):
                raise HTTPException(status_code=403, detail="cannot set superadmin app role")
        elif app_role == AppAccessRole.ADMIN:
            if not _actor_has_control_permission(db, actor, "admin_set_user_app_role_admin"):
                raise HTTPException(status_code=403, detail="cannot set admin app role")
        elif app_role != AppAccessRole.USER:
            raise HTTPException(status_code=400, detail="invalid app_role")
    user.app_role = app_role

    requested_roles = sorted(_legacy_roles_for_identity(primary_team, seniority, app_role), key=lambda r: r.value)

    role_rows = db.scalars(select(Role).where(Role.name.in_(requested_roles))).all()
    role_by_name = {r.name: r for r in role_rows}
    missing = [r.value for r in requested_roles if r not in role_by_name]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing role records: {', '.join(sorted(set(missing)))}")

    db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id))
    seen = set()
    for role_name in requested_roles:
        if role_name in seen:
            continue
        seen.add(role_name)
        db.add(UserRoleAssignment(user_id=user.id, role_id=role_by_name[role_name].id))

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="user",
            entity_id=user.id,
            action="user_roles_updated",
            meta_json={"roles": sorted([r.value for r in seen]), **updates_meta},
        )
    )
    db.commit()
    return {
        "item": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "is_active": bool(user.is_active),
                "roles": sorted([r.value for r in seen]),
                "primary_team": user.primary_team.value,
                "seniority": user.seniority.value,
                "app_role": user.app_role.value,
            }
        }


@router.delete("/admin/users/{user_id}")
def admin_remove_user(user_id: str, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    if not _actor_has_control_permission(db, actor, "admin_remove_user"):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user.id == actor.user_id:
        raise HTTPException(status_code=400, detail="cannot remove yourself")

    user.is_active = False
    db.execute(delete(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id))
    db.execute(delete(CampaignAssignment).where(CampaignAssignment.user_id == user.id))
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="user",
            entity_id=user.id,
            action="user_removed",
            meta_json={"email": user.email},
        )
    )
    db.commit()
    return {"ok": True}


@router.get("/demo/users")
def demo_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    mapped = {}
    for user in users:
        email = user.email.lower()
        if email.startswith("am@"):
            mapped["am"] = user.id
        elif email.startswith("ops@"):
            mapped["ops"] = user.id
        elif email.startswith("cm@"):
            mapped["cm"] = user.id
        elif email.startswith("cc@"):
            mapped["cc"] = user.id
        elif email.startswith("dn@"):
            mapped["dn"] = user.id
        elif email.startswith("mm@"):
            mapped["mm"] = user.id
        elif email.startswith("sales@"):
            mapped["sales"] = user.id
    return mapped


@router.get("/users/{user_id}/work-queue")
def get_user_work_queue(user_id: str, db: Session = Depends(get_db)):
    steps = db.scalars(
        select(WorkflowStep).where(WorkflowStep.next_owner_user_id == user_id).order_by(WorkflowStep.current_due.asc())
    ).all()

    return {
        "user_id": user_id,
        "deprecated": True,
        "items": [
            {
                "workflow_step_id": s.display_id,
                "name": s.name,
                "current_due": s.current_due.isoformat() if s.current_due else None,
                "waiting_on_type": s.waiting_on_type.value if s.waiting_on_type else None,
                "blocker_reason": s.blocker_reason,
            }
            for s in steps
        ],
    }


@router.get("/my-work")
def get_my_work(actor_user_id: str, role: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    try:
        role_name = RoleName(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid role") from exc

    if role_name not in actor.roles and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor does not hold selected role")

    payload = MyWorkQueueService(db).build(actor_user_id)

    queue_items = [item for arr in (payload.get("queues") or {}).values() for item in (arr or [])]
    step_display_ids = sorted(
        {
            str(i.get("step", {}).get("id"))
            for i in queue_items
            if i.get("step", {}).get("id")
        }
    )
    steps_by_display = (
        {
            s.display_id: s
            for s in db.scalars(select(WorkflowStep).where(WorkflowStep.display_id.in_(step_display_ids))).all()
        }
        if step_display_ids
        else {}
    )
    step_ids = [s.id for s in steps_by_display.values()]
    effort_rows = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all() if step_ids else []
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    for effort in effort_rows:
        efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
    user_ids = {actor_user_id}
    for step in steps_by_display.values():
        if step.next_owner_user_id:
            user_ids.add(step.next_owner_user_id)
    for effort in effort_rows:
        if effort.assigned_user_id:
            user_ids.add(effort.assigned_user_id)
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(sorted(user_ids)))).all()} if user_ids else {}
    deliverable_identifiers = sorted(
        {
            str(i.get("deliverable", {}).get("id"))
            for i in queue_items
            if i.get("deliverable", {}).get("id")
        }
    )
    deliverables = (
        db.scalars(
            select(Deliverable).where(
                (Deliverable.display_id.in_(deliverable_identifiers))
                | (Deliverable.id.in_(deliverable_identifiers))
            )
        ).all()
        if deliverable_identifiers
        else []
    )
    deliverable_health = _evaluate_deliverable_health_batch(db, deliverables)

    for key, arr in (payload.get("queues") or {}).items():
        normalized_arr = []
        for item in (arr or []):
            step_info = dict(item.get("step") or {})
            step = steps_by_display.get(step_info.get("id"))
            if step:
                step_info["module_type"] = _step_module_type(step)
                step_info["status"] = _normalize_step_status(step).value
                step_info["health"] = _normalize_step_health(step).value
                step_info["owner_initials"] = _initials_for_user_id(step.next_owner_user_id, users_by_id)
                step_info["participant_initials"] = _participant_initials_for_step(step, efforts_by_step, users_by_id)
            deliverable_info = dict(item.get("deliverable") or {})
            if deliverable_info.get("status"):
                try:
                    d_status = DeliverableStatus(deliverable_info["status"])
                    deliverable_info["status"] = _normalize_deliverable_status(d_status).value
                except ValueError:
                    pass
            d_id = str(deliverable_info.get("id") or "")
            d_health = deliverable_health.get(d_id) if d_id else None
            if d_health:
                deliverable_info["health"] = d_health["health"]
                deliverable_info["health_reason"] = d_health["health_reason"]
                deliverable_info["buffer_working_days_remaining"] = d_health["buffer_working_days_remaining"]
                deliverable_info["is_not_due"] = d_health["is_not_due"]
            normalized_arr.append({**item, "step": step_info, "deliverable": deliverable_info})
        payload["queues"][key] = normalized_arr
    return {
        "role": role_name.value,
        **payload,
    }


@router.post("/campaigns/{campaign_id}/sow-change-requests")
def create_sow_change_request(campaign_id: str, payload: SowChangeCreateIn, actor_user_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.CM, RoleName.AM, RoleName.HEAD_OPS, RoleName.ADMIN})
    if payload.requested_by_user_id != actor_user_id and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor must match requested_by_user_id unless admin")

    req = ChangeControlService(db).create_request(
        campaign_id=campaign.id,
        requested_by_user_id=payload.requested_by_user_id,
        impact_scope_json=payload.impact_scope_json,
    )
    db.commit()
    return {"id": req.display_id, "status": req.status}


@router.post("/sow-change-requests/{request_id}/decide")
def decide_sow_change_request(request_id: str, payload: SowChangeApproveIn, actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.HEAD_SALES, RoleName.ADMIN})
    if payload.approver_user_id != actor_user_id and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor must match approver_user_id unless admin")
    requested_role = RoleName(payload.approver_role)
    if requested_role not in actor.roles and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor does not hold the requested approver_role")

    try:
        req = ChangeControlService(db).apply_approval(
            request_id=request_id,
            approver_user_id=payload.approver_user_id,
            approver_role=requested_role,
            decision=payload.decision,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    return {"id": req.display_id, "status": req.status, "activated_at": req.activated_at}


@router.post("/deliverables/{deliverable_id}/ready-to-publish")
def mark_ready_to_publish(deliverable_id: str, actor_user_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    campaign = _campaign_for_deliverable(db, deliverable)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_campaign_member_or_roles(
        actor=actor,
        campaign=campaign,
        member_roles={RoleName.CM, RoleName.CC},
        fallback_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    )

    deliverable.status = DeliverableStatus.READY_TO_PUBLISH
    deliverable.ready_to_publish_by_user_id = actor_user_id
    deliverable.ready_to_publish_at = datetime.utcnow()
    db.commit()
    return {
        "deliverable_id": deliverable.id,
        "deliverable_display_id": deliverable.display_id,
        "status": deliverable.status.value,
        "ready_to_publish_by_user_id": deliverable.ready_to_publish_by_user_id,
        "ready_to_publish_at": deliverable.ready_to_publish_at,
    }


@router.post("/workflow-steps/{step_id}/complete")
def complete_workflow_step(step_id: str, payload: StepCompleteIn, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.CM, RoleName.CC, RoleName.CCS, RoleName.HEAD_OPS, RoleName.ADMIN})

    step = WorkflowEngineService(db).set_step_complete(step_id=step_id, actor_user_id=payload.actor_user_id)
    db.commit()
    return {
        "id": step.display_id,
        "actual_done": step.actual_done,
        "current_due": step.current_due,
    }


@router.post("/workflow-steps/{step_id}/override-due")
def override_workflow_step_due(step_id: str, payload: StepOverrideDueIn, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "override_step_due",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    existing_step = _resolve_by_identifier(db, WorkflowStep, step_id)
    if not existing_step:
        raise HTTPException(status_code=404, detail="workflow step not found")
    original_due = existing_step.current_due
    step = WorkflowEngineService(db).override_step_due(step_id=step_id, current_due_iso=payload.current_due_iso)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="workflow_step",
            entity_id=step.id,
            action="workflow_step_due_overridden",
            meta_json={
                "step_display_id": step.display_id,
                "old_due": original_due.isoformat() if original_due else None,
                "new_due": step.current_due.isoformat() if step.current_due else None,
                "reason_code": payload.reason_code,
            },
        )
    )
    db.commit()
    return {
        "id": step.display_id,
        "current_due": step.current_due,
        "reason_code": payload.reason_code,
    }


@router.patch("/workflow-steps/{step_id}/manage")
def manage_workflow_step(step_id: str, payload: StepManageIn, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    has_step_control = _actor_has_control_permission(
        db,
        actor,
        "manage_step",
        fallback_allowed_roles={RoleName.CM, RoleName.CC, RoleName.CCS, RoleName.HEAD_OPS, RoleName.ADMIN},
    )
    touches_non_date_fields = any(
        [
            payload.status is not None,
            payload.next_owner_user_id is not None,
            payload.waiting_on_user_id is not None,
            payload.blocker_reason is not None,
        ]
    )
    if touches_non_date_fields and not has_step_control:
        raise HTTPException(status_code=403, detail="insufficient role permissions")
    if payload.current_due_iso or payload.current_start_iso:
        can_manage_step_dates = _actor_has_control_permission(
            db,
            actor,
            "manage_step_dates",
            fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
        ) or _actor_has_control_permission(
            db,
            actor,
            "override_step_due",
            fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
        )
        if not can_manage_step_dates:
            raise HTTPException(status_code=403, detail="insufficient role permissions to edit step dates")
    if payload.status:
        allowed = {
            "not_started",
            "in_progress",
            "on_hold",
            "blocked_client",
            "blocked_internal",
            "blocked_dependency",
            "done",
            "cancelled",
            # Backward-compatible aliases:
            "complete",
            "reopen",
            "clear_blocker",
        }
        if payload.status.strip().lower() not in allowed:
            raise HTTPException(status_code=400, detail="unsupported status action")
    existing_step = _resolve_by_identifier(db, WorkflowStep, step_id)
    if not existing_step:
        raise HTTPException(status_code=404, detail="workflow step not found")
    previous_status = _normalize_step_status(existing_step).value
    previous_health = _normalize_step_health(existing_step).value

    step = WorkflowEngineService(db).manage_step(
        step_id=step_id,
        actor_user_id=payload.actor_user_id,
        status=payload.status,
        next_owner_user_id=payload.next_owner_user_id,
        waiting_on_user_id=payload.waiting_on_user_id,
        blocker_reason=payload.blocker_reason,
        current_start_iso=payload.current_start_iso,
        current_due_iso=payload.current_due_iso,
    )
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="workflow_step",
            entity_id=step.id,
            action="workflow_step_managed",
            meta_json={
                "step_display_id": step.display_id,
                "status_action": payload.status,
                "legacy_status_before": previous_status,
                "legacy_health_before": previous_health,
                "normalized_status_after": _normalize_step_status(step).value,
                "normalized_health_after": _normalize_step_health(step).value,
                "next_owner_user_id": payload.next_owner_user_id,
                "waiting_on_user_id": payload.waiting_on_user_id,
                "waiting_on_type": step.waiting_on_type.value if step.waiting_on_type else None,
                "current_start": step.current_start.isoformat() if step.current_start else None,
                "current_due": step.current_due.isoformat() if step.current_due else None,
            },
        )
    )
    db.commit()
    users_by_id = {}
    participant_initials: list[str] = []
    if step.next_owner_user_id:
        owner = db.get(User, step.next_owner_user_id)
        if owner:
            users_by_id[owner.id] = owner
    effort_rows = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id == step.id)).all()
    for effort in effort_rows:
        if effort.assigned_user_id and effort.assigned_user_id not in users_by_id:
            user = db.get(User, effort.assigned_user_id)
            if user:
                users_by_id[user.id] = user
    if effort_rows:
        participant_initials = _participant_initials_for_step(step, {step.id: effort_rows}, users_by_id)
    return {
        "id": step.display_id,
        "module_type": _step_module_type(step),
        "status": _normalize_step_status(step).value,
        "health": _normalize_step_health(step).value,
        "step_state": _normalize_step_status(step).value,
        "next_owner_user_id": step.next_owner_user_id,
        "owner_initials": _initials_for_user_id(step.next_owner_user_id, users_by_id),
        "participant_initials": participant_initials,
        "waiting_on_type": step.waiting_on_type.value if step.waiting_on_type else None,
        "waiting_on_user_id": step.waiting_on_user_id,
        "blocker_reason": step.blocker_reason,
        "current_start": step.current_start.isoformat() if step.current_start else None,
        "current_due": step.current_due.isoformat() if step.current_due else None,
        "actual_done": step.actual_done.isoformat() if step.actual_done else None,
    }


@router.post("/jobs/run-ops-risk-capacity")
def run_ops_risk_capacity_job(actor_user_id: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})

    summary = OpsJobService(db).run_all()
    db.commit()
    return {
        "capacity_rows_upserted": summary.capacity_rows_upserted,
        "over_capacity_rows": summary.over_capacity_rows,
        "system_risks_opened_or_updated": summary.system_risks_opened_or_updated,
        "escalations_opened": summary.escalations_opened,
    }


@router.get("/capacity-ledger")
def list_capacity_ledger(db: Session = Depends(get_db)):
    rows = db.scalars(select(CapacityLedger).order_by(CapacityLedger.week_start.desc())).all()
    return {
        "items": [
            {
                "id": r.display_id,
                "role_name": r.role_name.value,
                "week_start": r.week_start.isoformat(),
                "capacity_hours": r.capacity_hours,
                "planned_hours": r.planned_hours,
                "active_planned_hours": r.active_planned_hours,
                "forecast_planned_hours": r.forecast_planned_hours,
                "is_over_capacity": r.planned_hours > r.capacity_hours,
                "override_requested": r.override_requested,
                "override_requested_at": r.override_requested_at.isoformat() if r.override_requested_at else None,
                "override_approved": r.override_approved,
                "override_decided_at": r.override_decided_at.isoformat() if r.override_decided_at else None,
                "override_reason": r.override_reason,
            }
            for r in rows
        ]
    }


@router.get("/capacity/matrix")
def capacity_matrix(
    weeks: int = 4,
    granularity: str = "week",
    start_week: str | None = None,
    include_items: bool = False,
    db: Session = Depends(get_db),
):
    granularity = (granularity or "week").strip().lower()
    if granularity not in {"week", "day"}:
        raise HTTPException(status_code=400, detail="granularity must be week or day")
    if granularity == "day":
        if weeks != 1:
            raise HTTPException(status_code=400, detail="weeks must be 1 for day granularity")
    elif weeks not in {4, 13}:
        raise HTTPException(status_code=400, detail="weeks must be 4 or 13 for week granularity")

    if start_week:
        try:
            anchor = date.fromisoformat(start_week)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="start_week must be YYYY-MM-DD") from exc
    else:
        today = date.today()
        anchor = today - timedelta(days=today.weekday())
    anchor = anchor - timedelta(days=anchor.weekday())

    calendar = build_default_working_calendar()
    if granularity == "day":
        bucket_starts = [anchor + timedelta(days=i) for i in range(7) if calendar.is_working_day(anchor + timedelta(days=i))]
        week_starts = [anchor]
        end_exclusive = anchor + timedelta(days=7)
    else:
        week_starts = [anchor + timedelta(days=7 * i) for i in range(weeks)]
        bucket_starts = list(week_starts)
        end_exclusive = anchor + timedelta(days=7 * weeks)

    bucket_set = set(bucket_starts)
    week_set = set(week_starts)

    rows = db.scalars(
        select(CapacityLedger).where(
            CapacityLedger.week_start >= anchor,
            CapacityLedger.week_start < end_exclusive,
        )
    ).all()
    if not rows:
        any_ledger_rows = db.scalar(select(func.count()).select_from(CapacityLedger)) or 0
        if any_ledger_rows == 0:
            open_steps_count = db.scalar(select(func.count()).select_from(WorkflowStep).where(WorkflowStep.actual_done.is_(None))) or 0
            if open_steps_count > 0:
                OpsJobService(db).run_all()
                db.flush()
                rows = db.scalars(
                    select(CapacityLedger).where(
                        CapacityLedger.week_start >= anchor,
                        CapacityLedger.week_start < end_exclusive,
                    )
                ).all()

    row_user_ids = {r.user_id for r in rows}
    assigned_user_ids = set(db.scalars(select(CampaignAssignment.user_id).distinct()).all())
    user_ids = sorted(row_user_ids.union(assigned_user_ids))
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    role_rows = (
        db.execute(
            select(UserRoleAssignment.user_id, Role.name)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(UserRoleAssignment.user_id.in_(user_ids))
        ).all()
        if user_ids
        else []
    )
    user_role_map: dict[str, set[str]] = {}
    for user_id, role_name in role_rows:
        user_role_map.setdefault(user_id, set()).add(str(role_name.value if hasattr(role_name, "value") else role_name))

    def _cell_default():
        return {
            "capacity_hours": 0.0,
            "forecast_planned_hours": 0.0,
            "active_planned_hours": 0.0,
            "is_over_capacity": False,
            "ledger_id": None,
            "override_requested": False,
            "override_approved": False,
            "items_preview": [],
            "items_total": 0,
            "items": [],
        }

    cells: dict[str, dict] = {}
    role_load: dict[str, dict[str, float]] = {}
    assignment_role_load: dict[str, dict[str, float]] = {}
    capacity_service = CapacityService(db)

    def _per_day_factor(week_start: date) -> dict[date, float]:
        weights: dict[date, float] = {}
        working_days: list[date] = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            if calendar.is_working_day(d):
                working_days.append(d)
        if not working_days:
            return weights
        each = 1.0 / float(len(working_days))
        for d in working_days:
            weights[d] = each
        return weights

    def _merge_cell_payload(key: str, row_payload: dict) -> None:
        existing = cells.get(key)
        if not existing:
            cells[key] = row_payload
            return
        existing["capacity_hours"] += float(row_payload["capacity_hours"])
        existing["forecast_planned_hours"] += float(row_payload["forecast_planned_hours"])
        existing["active_planned_hours"] += float(row_payload["active_planned_hours"])
        existing["is_over_capacity"] = float(existing["forecast_planned_hours"]) > float(existing["capacity_hours"])
        existing["override_requested"] = existing["override_requested"] or bool(row_payload["override_requested"])
        existing["override_approved"] = existing["override_approved"] or bool(row_payload["override_approved"])
        if not existing["ledger_id"]:
            existing["ledger_id"] = row_payload["ledger_id"]

    for r in rows:
        if granularity == "day":
            day_weights = _per_day_factor(r.week_start)
            for d in bucket_starts:
                if d not in day_weights:
                    continue
                factor = day_weights[d]
                key = f"{r.user_id}:{d.isoformat()}"
                payload = _cell_default()
                payload.update(
                    {
                        "capacity_hours": float(r.capacity_hours) * factor,
                        "forecast_planned_hours": float(r.forecast_planned_hours) * factor,
                        "active_planned_hours": float(r.active_planned_hours) * factor,
                        "is_over_capacity": (float(r.forecast_planned_hours) * factor) > (float(r.capacity_hours) * factor),
                        "ledger_id": r.display_id,
                        "override_requested": r.override_requested,
                        "override_approved": r.override_approved,
                    }
                )
                _merge_cell_payload(key, payload)
        else:
            key = f"{r.user_id}:{r.week_start.isoformat()}"
            payload = _cell_default()
            payload.update(
                {
                    "capacity_hours": float(r.capacity_hours),
                    "forecast_planned_hours": float(r.forecast_planned_hours),
                    "active_planned_hours": float(r.active_planned_hours),
                    "is_over_capacity": float(r.forecast_planned_hours) > float(r.capacity_hours),
                    "ledger_id": r.display_id,
                    "override_requested": r.override_requested,
                    "override_approved": r.override_approved,
                }
            )
            cells[key] = payload
        role_load.setdefault(r.user_id, {})
        role_load[r.user_id][r.role_name.value] = role_load[r.user_id].get(r.role_name.value, 0.0) + float(
            r.forecast_planned_hours
        )

    if user_ids:
        assignments = db.scalars(select(CampaignAssignment).where(CampaignAssignment.user_id.in_(user_ids))).all()
        for a in assignments:
            assignment_role_load.setdefault(a.user_id, {})
            assignment_role_load[a.user_id][a.role_name.value] = assignment_role_load[a.user_id].get(a.role_name.value, 0.0) + 1.0

    def _weekly_capacity_for_role(role_value: str) -> float:
        try:
            return float(capacity_service.evaluate(RoleName(role_value), 0.0).capacity_hours)
        except Exception:
            return 40.0

    def _primary_capacity_role_for_user(uid: str) -> str:
        explicit_roles = user_role_map.get(uid) or set()
        # Prefer direct user role assignments first; these are user baseline truth.
        for role_value in (
            RoleName.CC.value,
            RoleName.CM.value,
            RoleName.AM.value,
            RoleName.CCS.value,
            RoleName.DN.value,
            RoleName.MM.value,
        ):
            if role_value in explicit_roles:
                return RoleName.CC.value if role_value == RoleName.CCS.value else role_value

        # Fallback to role load inference if explicit user-role assignment is missing.
        role_map = role_load.get(uid) or assignment_role_load.get(uid) or {}
        if role_map:
            inferred = max(role_map.items(), key=lambda kv: kv[1])[0]
            return RoleName.CC.value if inferred == RoleName.CCS.value else inferred
        return RoleName.CM.value

    weekly_capacity_by_user: dict[str, float] = {}
    primary_role_by_user: dict[str, str] = {}
    for uid in user_ids:
        primary_role = _primary_capacity_role_for_user(uid)
        primary_role_by_user[uid] = primary_role
        weekly_capacity = _weekly_capacity_for_role(primary_role)
        weekly_capacity_by_user[uid] = weekly_capacity

        if granularity == "day":
            weights = _per_day_factor(anchor)
            for d in bucket_starts:
                key = f"{uid}:{d.isoformat()}"
                if key in cells:
                    continue
                payload = _cell_default()
                payload["capacity_hours"] = weekly_capacity * float(weights.get(d, 0.0))
                cells[key] = payload
        else:
            for wk in bucket_starts:
                key = f"{uid}:{wk.isoformat()}"
                if key in cells:
                    continue
                payload = _cell_default()
                payload["capacity_hours"] = weekly_capacity
                cells[key] = payload

    # Enforce user baseline capacity as the source of truth for all visible cells.
    if granularity == "day":
        day_weights = _per_day_factor(anchor)
        for uid in user_ids:
            weekly_capacity = weekly_capacity_by_user.get(uid, _weekly_capacity_for_role(RoleName.CM.value))
            for d in bucket_starts:
                key = f"{uid}:{d.isoformat()}"
                cell = cells.get(key)
                if not cell:
                    continue
                baseline_capacity = weekly_capacity * float(day_weights.get(d, 0.0))
                cell["capacity_hours"] = baseline_capacity
                cell["is_over_capacity"] = float(cell["forecast_planned_hours"]) > float(cell["capacity_hours"])
    else:
        for uid in user_ids:
            weekly_capacity = weekly_capacity_by_user.get(uid, _weekly_capacity_for_role(RoleName.CM.value))
            for wk in bucket_starts:
                key = f"{uid}:{wk.isoformat()}"
                cell = cells.get(key)
                if not cell:
                    continue
                cell["capacity_hours"] = weekly_capacity
                cell["is_over_capacity"] = float(cell["forecast_planned_hours"]) > float(cell["capacity_hours"])

    if include_items and user_ids:
        open_steps = db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.actual_done.is_(None),
            )
        ).all()
        open_step_ids = [s.id for s in open_steps]
        effort_rows = db.scalars(
            select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(open_step_ids))
        ).all() if open_step_ids else []
        efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
        for effort in effort_rows:
            efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
        step_deliverable_ids = {_step_linked_deliverable(s) for s in open_steps if _step_linked_deliverable(s)}
        deliverables = (
            {d.id: d for d in db.scalars(select(Deliverable).where(Deliverable.id.in_(step_deliverable_ids))).all()}
            if step_deliverable_ids
            else {}
        )
        campaign_ids = {d.campaign_id for d in deliverables.values() if d.campaign_id}.union({s.campaign_id for s in open_steps if s.campaign_id})
        campaigns = (
            {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()} if campaign_ids else {}
        )
        assignment_rows = db.scalars(
            select(CampaignAssignment).where(CampaignAssignment.campaign_id.in_(campaign_ids))
        ).all() if campaign_ids else []
        assignment_map: dict[tuple[str, RoleName], str] = {
            (a.campaign_id, a.role_name): a.user_id for a in assignment_rows
        }

        grouped: dict[str, list[dict]] = {}
        def _item_bucket_day(step_date: date) -> date:
            return calendar.next_working_day_on_or_after(step_date)

        for step in open_steps:
            step_date = step.current_start or step.baseline_start or step.created_at.date()
            wk = step_date - timedelta(days=step_date.weekday())
            linked_deliverable_id = _step_linked_deliverable(step)
            d = deliverables.get(linked_deliverable_id) if linked_deliverable_id else None
            c = campaigns.get(step.campaign_id) if step.campaign_id else (campaigns.get(d.campaign_id) if d and d.campaign_id else None)
            if not c:
                continue
            step_efforts = [e for e in efforts_by_step.get(step.id, []) if float(e.hours or 0.0) > 0.0]
            if not step_efforts:
                fallback_user_id = assignment_map.get((c.id, step.owner_role)) or step.next_owner_user_id
                if fallback_user_id:
                    step_efforts = [
                        WorkflowStepEffort(
                            workflow_step_id=step.id,
                            role_name=step.owner_role,
                            hours=float(step.planned_hours or 0.0),
                            assigned_user_id=fallback_user_id,
                        )
                    ]

            for effort in step_efforts:
                forecast_owner_user_id = effort.assigned_user_id or assignment_map.get((c.id, effort.role_name))
                if not forecast_owner_user_id:
                    continue
                if granularity == "day":
                    bucket_date = _item_bucket_day(step_date)
                    if bucket_date not in bucket_set:
                        continue
                    bucket_key = f"{forecast_owner_user_id}:{bucket_date.isoformat()}"
                else:
                    if wk not in week_set:
                        continue
                    bucket_key = f"{forecast_owner_user_id}:{wk.isoformat()}"
                item_end = calendar.next_working_day_on_or_after(step.current_due or step_date)
                item = {
                    "step_id": step.display_id,
                    "step_name": step.name,
                    "step_kind": step.step_kind.value,
                    "step_status": _normalize_step_status(step).value,
                    "step_health": _normalize_step_health(step).value,
                    "step_owner_user_id": step.next_owner_user_id,
                    "step_owner_role": step.owner_role.value if step.owner_role else None,
                    "start": step_date.isoformat(),
                    "end": item_end.isoformat(),
                    "due": step.current_due.isoformat() if step.current_due else None,
                    "planned_hours": float(effort.hours or 0.0),
                    "load_kind": "forecast",
                    "effort_role": effort.role_name.value,
                    "waiting_on_type": step.waiting_on_type.value if step.waiting_on_type else None,
                    "campaign_id": c.display_id if c else None,
                    "campaign_title": c.title if c else None,
                    "parent_type": "stage" if step.stage_id else "campaign",
                    "deliverable_id": d.display_id if d else None,
                    "deliverable_title": d.title if d else None,
                    "linked_deliverable_id": d.display_id if d else None,
                    "linked_deliverable_title": d.title if d else None,
                }
                grouped.setdefault(bucket_key, []).append(item)

        for key, items in grouped.items():
            items.sort(key=lambda x: (x["due"] or "9999-12-31", x["step_name"]))
            cell = cells.get(key)
            if not cell:
                uid, wk = key.split(":")
                cell = _cell_default()
                cells[key] = cell
                if uid not in users:
                    continue
            cell["items_total"] = len(items)
            cell["items_preview"] = items[:3]
            cell["items"] = items

    user_rows = []
    for uid in user_ids:
        primary_role = primary_role_by_user.get(uid, "unknown")
        totals = {
            "forecast_hours": 0.0,
            "active_hours": 0.0,
            "capacity_hours": 0.0,
            "over_weeks": 0,
        }
        for bucket in bucket_starts:
            cell = cells.get(f"{uid}:{bucket.isoformat()}") or _cell_default()
            totals["forecast_hours"] += float(cell["forecast_planned_hours"])
            totals["active_hours"] += float(cell["active_planned_hours"])
            totals["capacity_hours"] += float(cell["capacity_hours"])
            if cell["is_over_capacity"]:
                totals["over_weeks"] += 1
        user_rows.append(
            {
                "user_id": uid,
                "user_name": users.get(uid).full_name if users.get(uid) else uid,
                "primary_role": primary_role,
                "totals": totals,
            }
        )

    user_rows.sort(key=lambda u: (u["user_name"] or "").lower())
    if granularity == "day":
        buckets = [{"bucket_start": d.isoformat(), "bucket_type": "day"} for d in bucket_starts]
    else:
        buckets = [{"bucket_start": d.isoformat(), "bucket_type": "week"} for d in bucket_starts]
    return {
        "weeks": [{"week_start": wk.isoformat()} for wk in week_starts],
        "buckets": buckets,
        "users": user_rows,
        "cells": cells,
        "start_week": anchor.isoformat(),
        "weeks_count": weeks,
        "granularity": granularity,
        "include_items": include_items,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.post("/capacity-ledger/{capacity_id}/request-override")
def request_capacity_override(capacity_id: str, payload: CapacityOverrideRequestIn, db: Session = Depends(get_db)):
    row = _resolve_by_identifier(db, CapacityLedger, capacity_id)
    if not row:
        raise HTTPException(status_code=404, detail="capacity row not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if payload.actor_user_id != row.user_id:
        authz.require_any(actor, {RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN})

    updated = CapacityOverrideService(db).request_override(row, payload.actor_user_id, payload.reason)
    db.commit()
    return {
        "id": updated.display_id,
        "override_requested": updated.override_requested,
        "override_reason": updated.override_reason,
    }


@router.post("/capacity-ledger/{capacity_id}/decide-override")
def decide_capacity_override(capacity_id: str, payload: CapacityOverrideDecisionIn, db: Session = Depends(get_db)):
    row = _resolve_by_identifier(db, CapacityLedger, capacity_id)
    if not row:
        raise HTTPException(status_code=404, detail="capacity row not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})

    updated = CapacityOverrideService(db).decide_override(
        row=row,
        actor_user_id=payload.actor_user_id,
        approve=payload.approve,
        reason=payload.reason,
    )
    db.commit()
    return {
        "id": updated.display_id,
        "override_requested": updated.override_requested,
        "override_approved": updated.override_approved,
        "override_reason": updated.override_reason,
    }


@router.get("/risks/system")
def list_system_risks(db: Session = Depends(get_db)):
    rows = db.scalars(select(SystemRisk).order_by(SystemRisk.created_at.desc())).all()
    return {
        "items": [
            {
                "id": r.display_id,
                "risk_code": r.risk_code,
                "severity": r.severity.value,
                "details": r.details,
                "is_open": r.is_open,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/risks/manual")
def list_manual_risks(db: Session = Depends(get_db)):
    rows = db.scalars(select(ManualRisk).order_by(ManualRisk.created_at.desc())).all()
    return {
        "items": [
            {
                "id": r.display_id,
                "severity": r.severity.value,
                "details": r.details,
                "mitigation_owner_user_id": r.mitigation_owner_user_id,
                "mitigation_due": r.mitigation_due.isoformat() if r.mitigation_due else None,
                "is_open": r.is_open,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/risks/manual")
def create_manual_risk(payload: ManualRiskCreateIn, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.AM, RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN})

    campaign = _resolve_by_identifier(db, Campaign, payload.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    try:
        severity = RiskSeverity(payload.severity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid severity") from exc

    public_ids = PublicIdService(db)
    risk = ManualRisk(
        display_id=public_ids.next_id(ManualRisk, "MRISK"),
        campaign_id=campaign.id,
        raised_by_user_id=payload.actor_user_id,
        severity=severity,
        details=payload.details,
        mitigation_owner_user_id=payload.mitigation_owner_user_id,
        mitigation_due=datetime.fromisoformat(payload.mitigation_due).date() if payload.mitigation_due else None,
        is_open=True,
    )
    db.add(risk)
    db.commit()
    return {"id": risk.display_id, "is_open": risk.is_open}


@router.patch("/risks/manual/{risk_id}")
def update_manual_risk(risk_id: str, payload: ManualRiskUpdateIn, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN})

    risk = _resolve_by_identifier(db, ManualRisk, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="manual risk not found")

    if payload.is_open is not None:
        risk.is_open = payload.is_open
    if payload.severity is not None:
        risk.severity = RiskSeverity(payload.severity)
    if payload.details is not None:
        risk.details = payload.details
    if payload.mitigation_owner_user_id is not None:
        risk.mitigation_owner_user_id = payload.mitigation_owner_user_id
    if payload.mitigation_due is not None:
        risk.mitigation_due = datetime.fromisoformat(payload.mitigation_due).date()

    db.commit()
    return {"id": risk.display_id, "is_open": risk.is_open}


@router.get("/escalations")
def list_escalations(db: Session = Depends(get_db)):
    rows = db.scalars(select(Escalation).order_by(Escalation.created_at.desc())).all()
    return {
        "items": [
            {
                "id": e.display_id,
                "risk_type": e.risk_type,
                "reason": e.reason,
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in rows
        ]
    }


@router.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(escalation_id: str, payload: EscalationResolveIn, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.HEAD_OPS, RoleName.ADMIN})

    escalation = _resolve_by_identifier(db, Escalation, escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="escalation not found")

    escalation.resolved_at = datetime.utcnow()
    db.commit()
    return {"id": escalation.display_id, "resolved_at": escalation.resolved_at}
