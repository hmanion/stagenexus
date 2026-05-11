from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Campaign, CampaignAssignment, Deliverable, Stage, WorkflowStep, WorkflowStepEffort
from app.services.timeline_health_service import TimelineHealthService


def refresh_campaign_health(db: Session, campaign_id: str) -> Campaign | None:
    campaign = db.get(Campaign, campaign_id)
    if not isinstance(campaign, Campaign):
        return None

    deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
    steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()
    assignments = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    stages = db.scalars(select(Stage).where(Stage.campaign_id == campaign.id)).all()

    step_ids = [step.id for step in steps]
    effort_rows = (
        db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
        if step_ids
        else []
    )
    efforts_by_step_id: dict[str, list[WorkflowStepEffort]] = {}
    for effort in effort_rows:
        efforts_by_step_id.setdefault(effort.workflow_step_id, []).append(effort)

    evaluation, _ = TimelineHealthService(db).evaluate_campaign(
        campaign=campaign,
        deliverables=deliverables,
        steps=steps,
        efforts_by_step_id=efforts_by_step_id,
        assignments=assignments,
        stages=stages,
    )

    campaign.health = evaluation.health
    campaign.health_reason = evaluation.health_reason
    campaign.health_updated_at = datetime.utcnow()
    return campaign


def refresh_many_campaign_health(db: Session, campaign_ids: list[str]) -> int:
    updated = 0
    for campaign_id in sorted({campaign_id for campaign_id in campaign_ids if campaign_id}):
        campaign = refresh_campaign_health(db, campaign_id)
        if campaign:
            updated += 1
    return updated
