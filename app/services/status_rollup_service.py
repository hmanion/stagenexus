from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Campaign, Stage, StatusSource, WorkflowStep
from app.services.timeline_health_service import TimelineHealthService


class StatusRollupService:
    def __init__(self, db: Session):
        self.db = db
        self.timeline_health = TimelineHealthService(db)

    def set_manual_campaign_status(self, campaign: Campaign, status: str, actor_user_id: str) -> Campaign:
        campaign.status = status
        campaign.status_source = StatusSource.MANUAL
        campaign.status_overridden_by_user_id = actor_user_id
        campaign.status_overridden_at = datetime.utcnow()
        return campaign

    def reset_campaign_to_derived(self, campaign: Campaign) -> Campaign:
        stages = self.db.scalars(select(Stage).where(Stage.campaign_id == campaign.id)).all()
        worst = "not_started"
        for stage in stages:
            status = str(stage.status.value if hasattr(stage.status, "value") else stage.status).lower()
            if status == "blocked_dependency":
                worst = "blocked_dependency"
                break
            if status in {"blocked_client", "blocked_internal"} and worst not in {"blocked_dependency"}:
                worst = status
            elif status == "in_progress" and worst == "not_started":
                worst = "in_progress"
            elif status == "done" and worst == "not_started":
                worst = "done"
        campaign.status = worst
        campaign.status_source = StatusSource.DERIVED
        campaign.status_overridden_by_user_id = None
        campaign.status_overridden_at = None
        return campaign

    def mark_stage_derived(self, stage: Stage) -> Stage:
        stage.status_source = StatusSource.DERIVED
        stage.status_overridden_by_user_id = None
        stage.status_overridden_at = None
        return stage

    def reset_parents_after_step_change(self, step: WorkflowStep) -> None:
        stage = self.db.get(Stage, step.stage_id) if step.stage_id else None
        if stage:
            self.mark_stage_derived(stage)
            campaign = self.db.get(Campaign, stage.campaign_id)
            if campaign:
                self.reset_campaign_to_derived(campaign)
