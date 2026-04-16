from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
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
    MilestoneSlaHealth,
    BenchmarkTarget,
    Escalation,
    ManualRisk,
    Milestone,
    PerformanceResult,
    Publication,
    Role,
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
from app.schemas.campaigns import (
    CampaignAssignmentsUpdateIn,
    CampaignDatesUpdateIn,
    CampaignDescendantStatusBulkIn,
    CampaignOut,
    CampaignStatusUpdateIn,
)
from app.schemas.admin import (
    AdminUserCreateIn,
    AdminUserRolesUpdateIn,
    OpsDefaultsUpdateIn,
    RolePermissionsUpdateIn,
)
from app.schemas.deals import (
    DealCreateIn,
    DealOut,
    OpsApproveIn,
    ScopeAmUpdateIn,
    ScopeContentUpdateIn,
    ScopeDeleteIn,
    ScopeTimeframeUpdateIn,
    SowChangeApproveIn,
    SowChangeCreateIn,
)
from app.schemas.milestones import MilestoneCompletionUpdateIn, MilestoneSlaOverrideIn, MilestoneUpdateIn
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
from app.services.deliverable_derivation_service import DeliverableDerivationService
from app.services.deal_service import DealService
from app.services.milestone_service import MilestoneService
from app.services.ops_job_service import OpsJobService
from app.services.workflow_engine_service import WorkflowEngineService
from app.services.id_service import PublicIdService
from app.services.my_work_queue_service import MyWorkQueueService
from app.services.calendar_service import build_default_working_calendar
from app.services.ops_defaults_service import OpsDefaultsService
from app.services.campaign_health_service import CampaignHealthService
from app.services.timeline_health_service import TimelineHealthService
from app.services.stage_integrity_service import StageIntegrityService
from app.services.status_rollup_service import StatusRollupService
from app.services.team_inference_service import TeamInferenceService


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


def _derived_deliverable_status(db: Session, deliverable: Deliverable) -> str:
    stage = DeliverableDerivationService(db).derive_operational_stage_status(deliverable)
    if stage == DeliverableStage.PLANNING:
        linked_steps = db.scalars(select(WorkflowStep).where(WorkflowStep.linked_deliverable_id == deliverable.id)).all()
        has_in_progress = any(
            str((s.normalized_status.value if hasattr(s.normalized_status, "value") else s.normalized_status) or "").lower() == "in_progress"
            for s in linked_steps
        )
        if not has_in_progress:
            return "not_started"
    return stage.value


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
    if getattr(deliverable, "operational_stage_status", None):
        return deliverable.operational_stage_status
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
        if m.due_date:
            targets.append(m.due_date)
        elif m.current_target_date:
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


def _delete_scope_graph(db: Session, deal_id: str) -> dict[str, int]:
    deleted = {
        "campaign_graph": 0,
        "campaigns": 0,
        "product_lines": 0,
        "attachments": 0,
        "activity_logs": 0,
        "comments": 0,
        "notes": 0,
        "scopes": 0,
    }
    campaign_ids = db.scalars(select(Campaign.id).where(Campaign.deal_id == deal_id)).all()
    for cid in campaign_ids:
        result = _delete_campaign_graph(db, cid)
        deleted["campaign_graph"] += sum(int(v or 0) for v in result.values())
        deleted["campaigns"] += int(result.get("campaigns", 0))

    pl_res = db.execute(delete(DealProductLine).where(DealProductLine.deal_id == deal_id))
    deleted["product_lines"] += int(pl_res.rowcount or 0)
    at_res = db.execute(delete(DealAttachment).where(DealAttachment.deal_id == deal_id))
    deleted["attachments"] += int(at_res.rowcount or 0)

    activity_res = db.execute(
        delete(ActivityLog).where(
            ActivityLog.entity_type == "scope",
            ActivityLog.entity_id == deal_id,
        )
    )
    deleted["activity_logs"] += int(activity_res.rowcount or 0)
    comments_res = db.execute(
        delete(Comment).where(
            Comment.entity_type == "scope",
            Comment.entity_id == deal_id,
        )
    )
    deleted["comments"] += int(comments_res.rowcount or 0)
    notes_res = db.execute(
        delete(Note).where(
            Note.entity_type == "scope",
            Note.entity_id == deal_id,
        )
    )
    deleted["notes"] += int(notes_res.rowcount or 0)
    scope_res = db.execute(delete(Deal).where(Deal.id == deal_id))
    deleted["scopes"] += int(scope_res.rowcount or 0)
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

    from app.api.routes.campaigns import dashboard_summary
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
        "editorial_subteams": ["cx", "uc"],
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
        "editorial_subteams": ["cx", "uc"],
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
def get_my_work(actor_user_id: str, role: str, include_mode: str = "owned_only", db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    try:
        role_name = RoleName(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid role") from exc

    if role_name not in actor.roles and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor does not hold selected role")

    include_participant = str(include_mode or "owned_only").strip().lower() in {"owned_and_participant", "owned+participant"}
    payload = MyWorkQueueService(db).build(actor_user_id, include_participant=include_participant)

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
        "include_mode": "owned_and_participant" if include_participant else "owned_only",
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
    if step.linked_deliverable_id:
        deliverable = db.get(Deliverable, step.linked_deliverable_id)
        if deliverable:
            DeliverableDerivationService(db).recompute_operational_stage_status(deliverable)
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
    existing_step = _resolve_by_identifier(db, WorkflowStep, step_id)
    if not existing_step:
        raise HTTPException(status_code=404, detail="workflow step not found")

    if payload.current_due_iso or payload.current_start_iso or payload.planned_work_date_iso:
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
    if payload.completion_date_iso is not None:
        is_owner = bool(existing_step.next_owner_user_id and existing_step.next_owner_user_id == payload.actor_user_id)
        can_manage_completion = is_owner or _actor_has_control_permission(
            db,
            actor,
            "manage_step_dates",
            fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
        )
        if not can_manage_completion:
            raise HTTPException(status_code=403, detail="only step owner can edit completion date")
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
        planned_work_date_iso=payload.planned_work_date_iso,
        completion_date_iso=payload.completion_date_iso,
    )
    if step.linked_deliverable_id:
        deliverable = db.get(Deliverable, step.linked_deliverable_id)
        if deliverable:
            DeliverableDerivationService(db).recompute_operational_stage_status(deliverable)
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
                "planned_work_date": step.planned_work_date.isoformat() if step.planned_work_date else None,
                "completion_date": step.completion_date.isoformat() if step.completion_date else None,
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
        "planned_work_date": step.planned_work_date.isoformat() if step.planned_work_date else None,
        "completion_date": step.completion_date.isoformat() if step.completion_date else None,
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
    actor_user_id: str | None = None,
    team_scope: str = "auto",
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
    if actor_user_id:
        actor = AuthzService(db).actor(actor_user_id)
        scope_mode = str(team_scope or "auto").strip().lower()
        restrict_to_managed_team = actor.seniority == SeniorityLevel.MANAGER or (
            actor.seniority == SeniorityLevel.LEADERSHIP and scope_mode == "managed"
        )
        if restrict_to_managed_team:
            actor_team_key = TeamInferenceService.canonical_team_key(
                actor.primary_team,
                getattr(actor, "editorial_subteam", None),
            )
            allowed_user_ids = {
                uid
                for uid, user in users.items()
                if TeamInferenceService.canonical_team_key(
                    user.primary_team,
                    getattr(user, "editorial_subteam", None),
                ) == actor_team_key
            }
            user_ids = sorted(allowed_user_ids)
            users = {uid: users[uid] for uid in user_ids}
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
            step_date = step.planned_work_date or step.current_start or step.baseline_start or step.created_at.date()
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
                    "planned_work_date": step.planned_work_date.isoformat() if step.planned_work_date else step_date.isoformat(),
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
    team_weekly: dict[str, dict[str, dict[str, float]]] = {}
    for uid in user_ids:
        user = users.get(uid)
        if not user:
            continue
        team_key = TeamInferenceService.canonical_team_key(user.primary_team, getattr(user, "editorial_subteam", None))
        team_weekly.setdefault(team_key, {})
        for bucket in bucket_starts:
            key = bucket.isoformat()
            cell = cells.get(f"{uid}:{key}") or _cell_default()
            aggregate = team_weekly[team_key].setdefault(
                key,
                {"forecast_planned_hours": 0.0, "active_planned_hours": 0.0, "capacity_hours": 0.0, "utilization_pct": 0.0},
            )
            aggregate["forecast_planned_hours"] += float(cell["forecast_planned_hours"])
            aggregate["active_planned_hours"] += float(cell["active_planned_hours"])
            aggregate["capacity_hours"] += float(cell["capacity_hours"])
    for team_key, bucket_map in team_weekly.items():
        for key, aggregate in bucket_map.items():
            cap = float(aggregate["capacity_hours"])
            aggregate["utilization_pct"] = round((float(aggregate["forecast_planned_hours"]) / cap * 100.0), 2) if cap > 0 else 0.0
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
        "team_weekly": team_weekly,
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
