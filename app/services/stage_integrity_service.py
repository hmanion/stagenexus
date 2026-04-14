from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

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
        stage_key = str(step.stage_name or "").strip().lower()
        if stage_key in self.STAGE_SET:
            if stage_key == "reporting" and not has_reporting_work:
                return "promotion"
            return stage_key

        name = str(step.name or "").strip().lower()
        if any(token in name for token in ("publish", "social promotion", "promot", "distribution")):
            return "promotion"
        if any(token in name for token in ("collect metrics", "draft report", "report internal review", "campaign review call", "engagement list", "lead total")):
            return "reporting" if has_reporting_work else "promotion"

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
                    if key in existing_by_stage.get(stage, {}):
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
                    )
                    existing_by_stage.setdefault(stage, {})[key] = created
            else:
                key = _step_key(step_name_base, None)
                if key in existing_by_stage.get(stage, {}):
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
                )
                existing_by_stage.setdefault(stage, {})[key] = created

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
        start = campaign.planned_start_date or campaign.created_at.date()
        due = campaign.planned_end_date or start
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
            waiting_on_type=WaitingOnType.DEPENDENCY,
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
