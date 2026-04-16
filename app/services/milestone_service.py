from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Campaign, Milestone, MilestoneSlaHealth, Stage, User
from app.services.calendar_service import build_default_working_calendar


STAGE_MILESTONE_MAP: dict[str, tuple[str, ...]] = {
    "planning": ("kickoff", "content_plan"),
    "production": ("interview", "writing", "internal_review", "client_review"),
    "promotion": ("publishing", "benchmark_met"),
    "reporting": ("report_available",),
}


@dataclass(frozen=True)
class MilestoneSlaEvaluation:
    sla_health: MilestoneSlaHealth
    reason: str


class MilestoneService:
    def __init__(self, db: Session):
        self.db = db
        self.calendar = build_default_working_calendar()

    def evaluate_sla(self, milestone: Milestone, today: date | None = None) -> MilestoneSlaEvaluation:
        today = today or date.today()
        due = milestone.due_date or milestone.current_target_date or milestone.baseline_date
        completed = milestone.completion_date or (milestone.achieved_at.date() if milestone.achieved_at else None)
        if due is None:
            return MilestoneSlaEvaluation(MilestoneSlaHealth.NOT_DUE, "missing_due_date")
        if completed is not None and completed <= due:
            return MilestoneSlaEvaluation(MilestoneSlaHealth.MET, "completed_on_or_before_due")
        if completed is not None and completed > due:
            return MilestoneSlaEvaluation(MilestoneSlaHealth.MISSED, "completed_after_due")
        if due < today:
            return MilestoneSlaEvaluation(MilestoneSlaHealth.MISSED, "past_due_uncompleted")
        return MilestoneSlaEvaluation(MilestoneSlaHealth.NOT_DUE, "not_yet_due")

    def refresh_sla(self, milestone: Milestone) -> Milestone:
        if milestone.sla_health_manual_override:
            return milestone
        evaluation = self.evaluate_sla(milestone)
        milestone.sla_health = evaluation.sla_health
        return milestone

    def set_completion_date(self, milestone: Milestone, completion_date: date | None) -> Milestone:
        milestone.completion_date = completion_date
        milestone.achieved_at = datetime.combine(completion_date, datetime.min.time()) if completion_date else None
        return self.refresh_sla(milestone)

    def override_sla_health(
        self,
        milestone: Milestone,
        *,
        actor_user_id: str,
        sla_health: MilestoneSlaHealth,
    ) -> Milestone:
        actor = self.db.get(User, actor_user_id)
        if not actor or str(actor.app_role.value if hasattr(actor.app_role, "value") else actor.app_role).lower() != "superadmin":
            raise HTTPException(status_code=403, detail="only superadmin can override milestone SLA health")
        milestone.sla_health = sla_health
        milestone.sla_health_manual_override = True
        milestone.sla_health_overridden_by_user_id = actor_user_id
        milestone.sla_health_overridden_at = datetime.utcnow()
        return milestone

    def clear_sla_override(self, milestone: Milestone) -> Milestone:
        milestone.sla_health_manual_override = False
        milestone.sla_health_overridden_by_user_id = None
        milestone.sla_health_overridden_at = None
        return self.refresh_sla(milestone)

    def reanchor_campaign_milestones(self, campaign: Campaign) -> int:
        if not campaign.planned_start_date:
            return 0
        milestones = self.db.scalars(select(Milestone).where(Milestone.campaign_id == campaign.id)).all()
        moved = 0
        for milestone in milestones:
            if milestone.offset_days_from_campaign_start is None:
                due = milestone.due_date or milestone.current_target_date or milestone.baseline_date
                if due:
                    milestone.offset_days_from_campaign_start = (due - campaign.planned_start_date).days
            if milestone.offset_days_from_campaign_start is None:
                continue
            new_due = campaign.planned_start_date.fromordinal(
                campaign.planned_start_date.toordinal() + int(milestone.offset_days_from_campaign_start)
            )
            # Milestones still respect working-day constraints.
            milestone.due_date = self.calendar.next_working_day_on_or_after(new_due)
            milestone.current_target_date = milestone.due_date
            self.refresh_sla(milestone)
            moved += 1
        return moved

    def ensure_stage_links_for_campaign(self, campaign_id: str) -> int:
        milestones = self.db.scalars(select(Milestone).where(Milestone.campaign_id == campaign_id)).all()
        if not milestones:
            return 0
        stages = self.db.scalars(select(Stage).where(Stage.campaign_id == campaign_id)).all()
        stage_by_name = {str(s.name or "").strip().lower(): s for s in stages}
        stage_for_milestone: dict[str, str] = {}
        for stage_name, milestone_names in STAGE_MILESTONE_MAP.items():
            for milestone_name in milestone_names:
                stage_for_milestone[milestone_name] = stage_name
        updated = 0
        for milestone in milestones:
            if milestone.stage_id:
                continue
            normalized_name = str(milestone.name or "").strip().lower()
            stage_name = stage_for_milestone.get(normalized_name)
            if not stage_name:
                continue
            stage = stage_by_name.get(stage_name)
            if not stage:
                continue
            milestone.stage_id = stage.id
            updated += 1
        return updated
