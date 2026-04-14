from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from datetime import date, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.domain import (
    Campaign,
    CampaignAssignment,
    CampaignType,
    DealProductLine,
    Deliverable,
    DeliverableType,
    GlobalHealth,
    GlobalStatus,
    Milestone,
    ProductModule,
    RoleName,
    Stage,
    TemplateVersion,
    WaitingOnType,
    WorkflowStep,
    WorkflowStepDependency,
    WorkflowStepEffort,
    WorkflowStepKind,
)
from app.services.id_service import PublicIdService
from app.services.ops_defaults_service import OpsDefaultsService
from app.services.timeline_service import TimelineService
from app.services.calendar_service import build_default_working_calendar
from app.services.workflow_engine_service import WorkflowEngineService


REPORTING_DELIVERABLE_TYPES = {
    DeliverableType.REPORT,
    DeliverableType.ENGAGEMENT_LIST,
    DeliverableType.LEAD_TOTAL,
}


@dataclass
class StageReconcileResult:
    created: int = 0
    removed: int = 0
    reparented_steps: int = 0


class StageIntegrityService:
    BASE_STAGES = ("planning", "production")
    STAGE_SET = ("planning", "production", "promotion", "reporting")

    def __init__(self, db: Session):
        self.db = db
        self.public_ids = PublicIdService(db)
        self.ops_defaults = OpsDefaultsService(db).get()
        self.timeline = TimelineService(build_default_working_calendar())

    def reconcile_campaign(self, campaign_id: str) -> StageReconcileResult:
        campaign = self.db.get(Campaign, campaign_id)
        if not campaign:
            return StageReconcileResult()

        result = StageReconcileResult()
        deliverables = self.db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign_id)).all()
        steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign_id)).all()
        linked_by_id = {d.id: d for d in deliverables}

        has_reporting_work = self._campaign_has_reporting_work(deliverables=deliverables, steps=steps, linked_by_id=linked_by_id)
        has_promotion_work = self._campaign_has_promotion_work(campaign=campaign, deliverables=deliverables)
        required = set(self.BASE_STAGES)
        if has_promotion_work:
            required.add("promotion")
        if has_reporting_work:
            required.add("reporting")

        stage_rows = self.db.scalars(select(Stage).where(Stage.campaign_id == campaign_id)).all()
        stage_map = {str(s.name).strip().lower(): s for s in stage_rows}

        for stage_name in sorted(required):
            if stage_name in stage_map:
                continue
            stage = Stage(
                display_id=self.public_ids.next_id(Stage, "STG"),
                campaign_id=campaign_id,
                name=stage_name,
            )
            self.db.add(stage)
            self.db.flush()
            stage_map[stage_name] = stage
            result.created += 1

        for step in steps:
            desired = self._desired_step_stage(
                step=step,
                linked_deliverable=linked_by_id.get(step.linked_deliverable_id or ""),
                has_reporting_work=has_reporting_work,
            )
            if desired not in required:
                desired = "promotion" if desired == "reporting" else "production"
            target_stage = stage_map.get(desired)
            if not target_stage:
                continue
            if step.stage_id != target_stage.id or (step.stage_name or "").strip().lower() != desired:
                step.stage_id = target_stage.id
                step.stage_name = desired
                result.reparented_steps += 1

        self._ensure_phase_template_steps(
            campaign=campaign,
            deliverables=deliverables,
            has_promotion_work=has_promotion_work,
            has_reporting_work=has_reporting_work,
            stage_map=stage_map,
        )
        self._stagger_publish_steps_for_campaign(campaign.id)

        if has_reporting_work:
            reporting_stage = stage_map.get("reporting")
            if reporting_stage:
                reporting_steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.stage_id == reporting_stage.id)).all()
                if not reporting_steps:
                    created = self._create_stage_step(
                        campaign=campaign,
                        stage=reporting_stage,
                        step_name="Collect metrics",
                        owner_role=RoleName.CM,
                        planned_hours=2.0,
                        step_kind=WorkflowStepKind.TASK,
                    )
                    if created:
                        result.created += 0

        if has_promotion_work:
            promotion_stage = stage_map.get("promotion")
            if promotion_stage:
                legacy_promotion_steps = self.db.scalars(
                    select(WorkflowStep).where(
                        WorkflowStep.stage_id == promotion_stage.id,
                        WorkflowStep.name == "Promotion coordination",
                    )
                ).all()
                self._delete_steps(legacy_promotion_steps)

        reporting_stage = stage_map.get("reporting")
        if reporting_stage and not has_reporting_work:
            reporting_steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.stage_id == reporting_stage.id)).all()
            if not reporting_steps:
                self.db.delete(reporting_stage)
                result.removed += 1
                stage_map.pop("reporting", None)

        promotion_stage = stage_map.get("promotion")
        if promotion_stage and not has_promotion_work:
            promotion_steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.stage_id == promotion_stage.id)).all()
            if not promotion_steps:
                self.db.delete(promotion_stage)
                result.removed += 1
                stage_map.pop("promotion", None)

        engine = WorkflowEngineService(self.db)
        for stage in stage_map.values():
            engine._refresh_stage_from_steps(stage.id)

        return result

    def stage_ids_for_campaign(
        self,
        campaign_id: str,
        required_stage_names: Iterable[str],
    ) -> dict[str, str]:
        stage_rows = self.db.scalars(select(Stage).where(Stage.campaign_id == campaign_id)).all()
        stage_map = {str(s.name).strip().lower(): s.id for s in stage_rows}
        created_any = False
        for stage_name in {str(n).strip().lower() for n in required_stage_names if str(n).strip()}:
            if stage_name in stage_map:
                continue
            if stage_name not in self.STAGE_SET:
                continue
            stage = Stage(
                display_id=self.public_ids.next_id(Stage, "STG"),
                campaign_id=campaign_id,
                name=stage_name,
            )
            self.db.add(stage)
            self.db.flush()
            stage_map[stage_name] = stage.id
            created_any = True
        if created_any:
            self.db.flush()
        return stage_map

    def _delete_steps(self, steps: list[WorkflowStep]) -> None:
        if not steps:
            return
        step_ids = [s.id for s in steps]
        self.db.execute(delete(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids)))
        self.db.execute(
            delete(WorkflowStepDependency).where(
                or_(
                    WorkflowStepDependency.predecessor_step_id.in_(step_ids),
                    WorkflowStepDependency.successor_step_id.in_(step_ids),
                )
            )
        )
        self.db.execute(delete(WorkflowStep).where(WorkflowStep.id.in_(step_ids)))

    def _campaign_has_reporting_work(
        self,
        deliverables: list[Deliverable],
        steps: list[WorkflowStep],
        linked_by_id: dict[str, Deliverable],
    ) -> bool:
        if any(d.deliverable_type in REPORTING_DELIVERABLE_TYPES for d in deliverables):
            return True
        for step in steps:
            linked = linked_by_id.get(step.linked_deliverable_id or "")
            if linked and linked.deliverable_type in REPORTING_DELIVERABLE_TYPES:
                return True
            stage_key = str(step.stage_name or "").strip().lower()
            if stage_key == "reporting":
                return True
            name = str(step.name or "").strip().lower()
            if any(token in name for token in ("collect metrics", "report", "engagement list", "lead total")):
                return True
        return False

    def _campaign_has_promotion_work(self, campaign: Campaign, deliverables: list[Deliverable]) -> bool:
        promotion_types = {
            DeliverableType.ARTICLE,
            DeliverableType.VIDEO,
            DeliverableType.CLIP,
            DeliverableType.SHORT,
            DeliverableType.DISPLAY_ASSET,
            DeliverableType.LANDING_PAGE,
            DeliverableType.EMAIL,
        }
        if any(d.deliverable_type in promotion_types for d in deliverables):
            return True
        module_rows = self.db.scalars(select(ProductModule).where(ProductModule.campaign_id == campaign.id, ProductModule.enabled.is_(True))).all()
        return any(str(m.module_name or "").strip().lower() in {"reach", "promotion"} for m in module_rows)

    def _desired_step_stage(
        self,
        step: WorkflowStep,
        linked_deliverable: Deliverable | None,
        has_reporting_work: bool,
    ) -> str:
        name = str(step.name or "").strip().lower()
        if any(token in name for token in ("publish", "social promotion", "promot", "distribution")):
            return "promotion"
        if any(token in name for token in ("collect metrics", "draft report", "report internal review", "campaign review call", "engagement list", "lead total")):
            return "reporting" if has_reporting_work else "promotion"

        stage_key = str(step.stage_name or "").strip().lower()
        if stage_key in self.STAGE_SET:
            if stage_key == "reporting" and not has_reporting_work:
                return "promotion"
            return stage_key

        if linked_deliverable:
            if linked_deliverable.deliverable_type in REPORTING_DELIVERABLE_TYPES:
                return "reporting" if has_reporting_work else "promotion"
            if linked_deliverable.deliverable_type == DeliverableType.DISPLAY_ASSET:
                return "promotion"
            return "production"
        if any(token in name for token in ("kick-off", "briefing", "interview", "content plan")):
            return "planning"
        if any(token in name for token in ("report",)):
            return "reporting" if has_reporting_work else "promotion"
        return "production"

    def _ensure_phase_template_steps(
        self,
        campaign: Campaign,
        deliverables: list[Deliverable],
        has_promotion_work: bool,
        has_reporting_work: bool,
        stage_map: dict[str, Stage],
    ) -> None:
        template = self.db.get(TemplateVersion, campaign.template_version_id) if campaign.template_version_id else None
        rows = list((template.workflow_json or {}).get("csv_stage_steps") or []) if template else []
        if not rows:
            return

        line = self.db.scalar(
            select(DealProductLine)
            .where(
                DealProductLine.deal_id == campaign.deal_id,
                DealProductLine.product_type == campaign.campaign_type,
                DealProductLine.tier == campaign.tier,
            )
            .order_by(DealProductLine.created_at.asc())
        )
        if not line:
            return

        editorial_types = {
            DeliverableType.ARTICLE,
            DeliverableType.VIDEO,
            DeliverableType.CLIP,
            DeliverableType.SHORT,
        }
        editorial_deliverables = [d for d in deliverables if d.deliverable_type in editorial_types]
        # Cleanup legacy publish steps incorrectly left in production stage.
        production_stage = stage_map.get("production")
        if production_stage:
            legacy_production_publish = self.db.scalars(
                select(WorkflowStep).where(
                    WorkflowStep.stage_id == production_stage.id,
                    WorkflowStep.linked_deliverable_id.is_not(None),
                    WorkflowStep.name.ilike("Publish%"),
                )
            ).all()
            self._delete_steps(legacy_production_publish)
        milestones = self.db.scalars(select(Milestone).where(Milestone.campaign_id == campaign.id)).all()
        milestone_map = {
            m.name: (m.current_target_date or m.baseline_date)
            for m in milestones
            if (m.current_target_date or m.baseline_date)
        }
        stage_anchor = {
            "planning": milestone_map.get("kickoff") or campaign.planned_start_date or campaign.created_at.date(),
            "production": milestone_map.get("content_plan") or milestone_map.get("kickoff") or campaign.planned_start_date or campaign.created_at.date(),
            "promotion": milestone_map.get("publishing") or milestone_map.get("content_plan") or campaign.planned_start_date or campaign.created_at.date(),
            "reporting": milestone_map.get("reporting") or milestone_map.get("publishing") or campaign.planned_end_date or campaign.planned_start_date or campaign.created_at.date(),
        }
        def _step_key(step_name: str, linked_deliverable_id: str | None) -> tuple[str, str | None]:
            return (str(step_name or "").strip().lower(), linked_deliverable_id or None)

        existing_by_stage = {
            stage_name: {
                _step_key(str(s.name or ""), s.linked_deliverable_id): s
                for s in self.db.scalars(select(WorkflowStep).where(WorkflowStep.stage_id == stage.id)).all()
            }
            for stage_name, stage in stage_map.items()
        }

        for row in rows:
            if not self._row_applies_to_campaign(row, campaign, line):
                continue
            stage = str(row.get("stage") or "production").strip().lower()
            if stage not in {"promotion", "reporting"}:
                continue
            if stage == "reporting" and not has_reporting_work:
                continue
            if stage == "promotion" and not has_promotion_work:
                continue
            stage_rec = stage_map.get(stage)
            if not stage_rec:
                continue
            step_name_base = str(row.get("step_name") or "").strip()
            if not step_name_base:
                continue
            hours_by_role = {
                str(k): float(v)
                for k, v in (row.get("hours_by_role") or {}).items()
                if float(v or 0) > 0
            }
            owner_role = self._owner_role_from_hours(hours_by_role)
            step_kind = WorkflowStepKind(str(row.get("step_kind") or "task"))
            frequency = str(row.get("frequency") or "per_campaign")
            lower_step_name = step_name_base.lower()
            # Publish actions should always exist per content deliverable.
            if stage in {"production", "promotion"} and lower_step_name.startswith("publish"):
                frequency = "per_content_piece"
            if frequency == "per_content_piece":
                generic_key = _step_key(step_name_base, None)
                generic_step = existing_by_stage.get(stage, {}).pop(generic_key, None)
                if generic_step:
                    self._delete_steps([generic_step])
                for deliverable in editorial_deliverables:
                    if not self._row_applies_to_deliverable(row, deliverable):
                        continue
                    full_name = f"{step_name_base} · {deliverable.title}"
                    key = _step_key(full_name, deliverable.id)
                    dep_steps = self._resolve_dependency_steps(
                        campaign_id=campaign.id,
                        dep_names=[str(x).strip() for x in (row.get("dependencies") or [])],
                        target_deliverable_id=deliverable.id,
                    )
                    planned_start = stage_anchor.get(stage) or campaign.planned_start_date or campaign.created_at.date()
                    if dep_steps:
                        latest_due = max((s.current_due for s in dep_steps if s.current_due), default=planned_start)
                        planned_start = latest_due or planned_start
                    duration_days = self._duration_days_for_csv_step(step_name_base, step_kind)
                    existing_step = existing_by_stage.get(stage, {}).get(key)
                    if existing_step:
                        self._retime_step(
                            step=existing_step,
                            planned_start=planned_start,
                            duration_days=duration_days,
                            waiting_on_dependency=bool(dep_steps),
                        )
                        self._ensure_step_dependencies(existing_step, dep_steps)
                        continue
                    created = self._create_stage_step(
                        campaign=campaign,
                        stage=stage_rec,
                        step_name=full_name,
                        owner_role=owner_role,
                        planned_hours=max(float(sum(hours_by_role.values() or [0.0])), 1.0),
                        step_kind=step_kind,
                        linked_deliverable_id=deliverable.id,
                        hours_by_role=hours_by_role,
                        planned_start=planned_start,
                        duration_days=duration_days,
                        waiting_on_dependency=bool(dep_steps),
                    )
                    self._ensure_step_dependencies(created, dep_steps)
                    existing_by_stage.setdefault(stage, {})[key] = created
            else:
                key = _step_key(step_name_base, None)
                dep_steps = self._resolve_dependency_steps(
                    campaign_id=campaign.id,
                    dep_names=[str(x).strip() for x in (row.get("dependencies") or [])],
                    target_deliverable_id=None,
                )
                planned_start = stage_anchor.get(stage) or campaign.planned_start_date or campaign.created_at.date()
                if dep_steps:
                    latest_due = max((s.current_due for s in dep_steps if s.current_due), default=planned_start)
                    planned_start = latest_due or planned_start
                duration_days = self._duration_days_for_csv_step(step_name_base, step_kind)
                existing_step = existing_by_stage.get(stage, {}).get(key)
                if existing_step:
                    self._retime_step(
                        step=existing_step,
                        planned_start=planned_start,
                        duration_days=duration_days,
                        waiting_on_dependency=bool(dep_steps),
                    )
                    self._ensure_step_dependencies(existing_step, dep_steps)
                    continue
                created = self._create_stage_step(
                    campaign=campaign,
                    stage=stage_rec,
                    step_name=step_name_base,
                    owner_role=owner_role,
                    planned_hours=max(float(sum(hours_by_role.values() or [0.0])), 1.0),
                    step_kind=step_kind,
                    linked_deliverable_id=None,
                    hours_by_role=hours_by_role,
                    planned_start=planned_start,
                    duration_days=duration_days,
                    waiting_on_dependency=bool(dep_steps),
                )
                self._ensure_step_dependencies(created, dep_steps)
                existing_by_stage.setdefault(stage, {})[key] = created

    def _resolve_dependency_steps(
        self,
        campaign_id: str,
        dep_names: list[str],
        target_deliverable_id: str | None,
    ) -> list[WorkflowStep]:
        if not dep_names:
            return []
        all_steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign_id)).all()
        resolved: list[WorkflowStep] = []
        dep_names_norm = [d.strip().lower() for d in dep_names if d.strip()]
        for step in all_steps:
            base_name = str(step.name or "").split("·", 1)[0].strip().lower()
            if base_name not in dep_names_norm:
                continue
            # Per-content steps should primarily depend on same-deliverable chain.
            if target_deliverable_id and step.linked_deliverable_id and step.linked_deliverable_id != target_deliverable_id:
                continue
            resolved.append(step)
        return resolved

    def _ensure_step_dependencies(self, successor: WorkflowStep | None, predecessors: list[WorkflowStep]) -> None:
        if not successor or not predecessors:
            return
        existing = {
            (d.predecessor_step_id, d.successor_step_id)
            for d in self.db.scalars(
                select(WorkflowStepDependency).where(WorkflowStepDependency.successor_step_id == successor.id)
            ).all()
        }
        for predecessor in predecessors:
            pair = (predecessor.id, successor.id)
            if pair in existing:
                continue
            self.db.add(
                WorkflowStepDependency(
                    display_id=self.public_ids.next_id(WorkflowStepDependency, "DEP"),
                    predecessor_step_id=predecessor.id,
                    successor_step_id=successor.id,
                    dependency_type="finish_to_start",
                )
            )

    def _row_applies_to_campaign(self, row: dict, campaign: Campaign, line: DealProductLine) -> bool:
        applicability = row.get("applicability_by_product") or {}
        tier = str(campaign.tier or line.tier or "").strip().lower()
        if campaign.campaign_type == CampaignType.DEMAND:
            if campaign.demand_track == "capture":
                return tier in (applicability.get("demand_capture") or [])
            return (
                tier in (applicability.get("demand_create") or [])
                or tier in (applicability.get("demand_reach") or [])
            )
        if campaign.campaign_type == CampaignType.RESPONSE:
            return tier in (applicability.get("response") or [])
        if campaign.campaign_type == CampaignType.AMPLIFY:
            return tier in (applicability.get("amplify") or [])
        return tier in (applicability.get("display") or [])

    @staticmethod
    def _row_applies_to_deliverable(row: dict, deliverable: Deliverable) -> bool:
        step_name = str(row.get("step_name") or "").strip().lower()
        if "draft article" in step_name and deliverable.deliverable_type != DeliverableType.ARTICLE:
            return False
        if "article" in step_name and deliverable.deliverable_type != DeliverableType.ARTICLE:
            return False
        if "video" in step_name and deliverable.deliverable_type != DeliverableType.VIDEO:
            return False
        if "clip" in step_name and deliverable.deliverable_type != DeliverableType.CLIP:
            return False
        if "short" in step_name and deliverable.deliverable_type != DeliverableType.SHORT:
            return False
        return True

    @staticmethod
    def _owner_role_from_hours(hours_by_role: dict[str, float]) -> RoleName:
        ranking = []
        priority = {
            RoleName.CM: 0,
            RoleName.CC: 1,
            RoleName.AM: 2,
            RoleName.DN: 3,
            RoleName.MM: 4,
            RoleName.CCS: 5,
        }
        for key, val in hours_by_role.items():
            try:
                role = RoleName(key)
            except ValueError:
                continue
            ranking.append((float(val), -priority.get(role, 99), role))
        if not ranking:
            return RoleName.CM
        ranking.sort(reverse=True)
        return ranking[0][2]

    def _create_stage_step(
        self,
        campaign: Campaign,
        stage: Stage,
        step_name: str,
        owner_role: RoleName,
        planned_hours: float,
        step_kind: WorkflowStepKind,
        linked_deliverable_id: str | None = None,
        hours_by_role: dict[str, float] | None = None,
        planned_start: date | None = None,
        duration_days: int = 1,
        waiting_on_dependency: bool = False,
    ) -> WorkflowStep | None:
        existing = self.db.scalar(
            select(WorkflowStep).where(
                WorkflowStep.campaign_id == campaign.id,
                WorkflowStep.stage_id == stage.id,
                WorkflowStep.name == step_name,
                WorkflowStep.linked_deliverable_id == (linked_deliverable_id or None),
            )
        )
        if existing:
            return existing

        owner_user_id = self.db.scalar(
            select(CampaignAssignment.user_id).where(
                CampaignAssignment.campaign_id == campaign.id,
                CampaignAssignment.role_name == owner_role,
            )
        )
        start = planned_start or campaign.planned_start_date or campaign.created_at.date()
        _, due = self.timeline.plan_step_window(start, max(int(duration_days), 1))
        step = WorkflowStep(
            display_id=self.public_ids.next_id(WorkflowStep, "STEP"),
            campaign_id=campaign.id,
            stage_id=stage.id,
            linked_deliverable_id=linked_deliverable_id,
            deliverable_id=None,
            stage_name=str(stage.name or "").strip().lower(),
            name=step_name,
            step_kind=step_kind,
            owner_role=owner_role,
            planned_hours=float(planned_hours),
            planned_hours_baseline=float(planned_hours),
            baseline_start=start,
            baseline_due=due,
            current_start=start,
            current_due=due,
            stuck_threshold_days=3,
            next_owner_user_id=owner_user_id,
            waiting_on_type=WaitingOnType.DEPENDENCY if waiting_on_dependency else None,
            normalized_status=GlobalStatus.NOT_STARTED,
            normalized_health=GlobalHealth.NOT_STARTED,
        )
        self.db.add(step)
        self.db.flush()
        effort_map = {
            owner_role: float(planned_hours),
        }
        if hours_by_role:
            for key, hours in hours_by_role.items():
                try:
                    role = RoleName(key)
                except ValueError:
                    continue
                h = float(hours or 0.0)
                if h <= 0:
                    continue
                effort_map[role] = h
        for role, hours in effort_map.items():
            assigned_user_id = self.db.scalar(
                select(CampaignAssignment.user_id).where(
                    CampaignAssignment.campaign_id == campaign.id,
                    CampaignAssignment.role_name == role,
                )
            )
            self.db.add(
                WorkflowStepEffort(
                    display_id=self.public_ids.next_id(WorkflowStepEffort, "EFF"),
                    workflow_step_id=step.id,
                    role_name=role,
                    hours=float(hours),
                    assigned_user_id=assigned_user_id,
                )
            )
        return step

    def _retime_step(
        self,
        step: WorkflowStep,
        planned_start: date,
        duration_days: int,
        waiting_on_dependency: bool,
    ) -> None:
        _, due = self.timeline.plan_step_window(planned_start, max(int(duration_days), 1))
        step.baseline_start = planned_start
        step.current_start = planned_start
        step.baseline_due = due
        step.current_due = due
        step.waiting_on_type = WaitingOnType.DEPENDENCY if waiting_on_dependency else None

    def _duration_days_for_csv_step(self, step_name: str, step_kind: WorkflowStepKind) -> int:
        timeline_defaults = self.ops_defaults.get("timeline_defaults", {})
        low = step_name.strip().lower()
        if "draft article" in low:
            return max(1, int(timeline_defaults.get("writing_working_days", 8)))
        if step_kind == WorkflowStepKind.APPROVAL:
            if "client" in low:
                return max(1, int(timeline_defaults.get("client_review_working_days", 5)))
            return max(1, int(timeline_defaults.get("internal_review_working_days", 2)))
        if step_kind == WorkflowStepKind.CALL:
            return 1
        return 1

    @staticmethod
    def _is_publish_step_name(name: str | None) -> bool:
        value = str(name or "").strip().lower()
        return bool(value and "publish" in value)

    def _stagger_publish_steps_for_campaign(self, campaign_id: str) -> int:
        campaign = self.db.get(Campaign, campaign_id)
        if not campaign:
            return 0
        promotion_stage = self.db.scalar(
            select(Stage).where(Stage.campaign_id == campaign_id, Stage.name == "promotion")
        )
        if not promotion_stage:
            return 0
        steps = self.db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.campaign_id == campaign_id,
                WorkflowStep.stage_id == promotion_stage.id,
                WorkflowStep.linked_deliverable_id.is_not(None),
            )
        ).all()
        if not steps:
            return 0
        deliverable_ids = sorted({s.linked_deliverable_id for s in steps if s.linked_deliverable_id})
        deliverables = (
            {
                d.id: d
                for d in self.db.scalars(select(Deliverable).where(Deliverable.id.in_(deliverable_ids))).all()
            }
            if deliverable_ids
            else {}
        )
        eligible = []
        social_by_deliverable: dict[str, list[WorkflowStep]] = {}
        for step in steps:
            if step.actual_done is not None:
                continue
            low_name = str(step.name or "").strip().lower()
            if "social promotion" in low_name and step.linked_deliverable_id:
                social_by_deliverable.setdefault(step.linked_deliverable_id, []).append(step)
            if not self._is_publish_step_name(step.name) or "social promotion" in low_name:
                continue
            deliverable = deliverables.get(step.linked_deliverable_id or "")
            if not deliverable:
                continue
            if deliverable.deliverable_type not in {DeliverableType.ARTICLE, DeliverableType.VIDEO}:
                continue
            eligible.append(step)
        if len(eligible) <= 1:
            return 0

        content_client_reviews = self.db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.campaign_id == campaign_id,
                WorkflowStep.name.ilike("Content client review%"),
            )
        ).all()
        approval_gate_due = max(
            (
                s.current_due or s.baseline_due or s.current_start or s.baseline_start
                for s in content_client_reviews
                if (s.current_due or s.baseline_due or s.current_start or s.baseline_start)
            ),
            default=None,
        )
        anchor_candidates = [s.current_start or s.baseline_start for s in eligible if (s.current_start or s.baseline_start)]
        anchor = approval_gate_due or (min(anchor_candidates) if anchor_candidates else (campaign.planned_start_date or date.today()))
        calendar = self.timeline.calendar

        dependency_rows = self.db.scalars(
            select(WorkflowStepDependency).where(
                WorkflowStepDependency.successor_step_id.in_([s.id for s in eligible])
            )
        ).all()
        predecessor_ids = sorted({d.predecessor_step_id for d in dependency_rows})
        predecessors = (
            {s.id: s for s in self.db.scalars(select(WorkflowStep).where(WorkflowStep.id.in_(predecessor_ids))).all()}
            if predecessor_ids
            else {}
        )
        deps_by_successor: dict[str, list[WorkflowStep]] = {}
        for dep in dependency_rows:
            predecessor = predecessors.get(dep.predecessor_step_id)
            if not predecessor:
                continue
            deps_by_successor.setdefault(dep.successor_step_id, []).append(predecessor)

        def _step_sort_key(step: WorkflowStep) -> tuple:
            deliverable = deliverables.get(step.linked_deliverable_id or "")
            dtype_rank = 0
            if deliverable and deliverable.deliverable_type == DeliverableType.VIDEO:
                dtype_rank = 1
            start = step.current_start or step.baseline_start or anchor
            return (start, dtype_rank, step.created_at, step.id)

        staggered_count = 0
        engine = WorkflowEngineService(self.db)
        sorted_eligible = sorted(eligible, key=_step_sort_key)
        for idx, step in enumerate(sorted_eligible):
            target_start = calendar.next_working_day_on_or_after(anchor + timedelta(days=(7 * idx)))
            predecessors_for_step = deps_by_successor.get(step.id, [])
            if predecessors_for_step:
                predecessor_due = max(
                    (
                        p.current_due
                        or p.baseline_due
                        or p.current_start
                        or p.baseline_start
                        for p in predecessors_for_step
                    ),
                    default=target_start,
                )
                target_start = calendar.next_working_day_on_or_after(max(target_start, predecessor_due))

            # Publish windows are short execution windows, not campaign-length spans.
            target_due = calendar.next_working_day_on_or_after(calendar.add_working_days(target_start, 1))
            if (
                step.current_start == target_start
                and step.current_due == target_due
                and step.baseline_start == target_start
                and step.baseline_due == target_due
            ):
                continue
            step.baseline_start = target_start
            step.current_start = target_start
            step.baseline_due = target_due
            step.current_due = target_due
            engine._recalculate_successor_chain(step)
            staggered_count += 1

            linked_deliverable_id = step.linked_deliverable_id or ""
            for social_step in social_by_deliverable.get(linked_deliverable_id, []):
                social_start = calendar.next_working_day_on_or_after(target_due)
                social_due = calendar.next_working_day_on_or_after(calendar.add_working_days(social_start, 1))
                if (
                    social_step.current_start == social_start
                    and social_step.current_due == social_due
                    and social_step.baseline_start == social_start
                    and social_step.baseline_due == social_due
                ):
                    continue
                social_step.baseline_start = social_start
                social_step.current_start = social_start
                social_step.baseline_due = social_due
                social_step.current_due = social_due
                engine._recalculate_successor_chain(social_step)
                staggered_count += 1
        return staggered_count
