from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Campaign, Deliverable, DeliverableStatus, WaitingOnType, WorkflowStep
from app.services.calendar_service import build_default_working_calendar


@dataclass(frozen=True)
class QueueBuckets:
    now: list[dict]
    next_10_working_days: list[dict]
    blocked: list[dict]
    awaiting_internal_review: list[dict]
    awaiting_client_review: list[dict]


class MyWorkQueueService:
    def __init__(self, db: Session):
        self.db = db
        self.calendar = build_default_working_calendar()

    def build(self, actor_user_id: str) -> dict:
        today = date.today()
        window_end = self.calendar.add_working_days(today, 10)

        steps = self.db.scalars(
            select(WorkflowStep)
            .where(
                WorkflowStep.actual_done.is_(None),
                WorkflowStep.next_owner_user_id == actor_user_id,
            )
            .order_by(WorkflowStep.current_due.asc())
        ).all()
        if not steps:
            return {
                "summary": {
                    "now": 0,
                    "next_10_working_days": 0,
                    "blocked": 0,
                    "awaiting_internal_review": 0,
                    "awaiting_client_review": 0,
                    "total": 0,
                },
                "queues": {
                    "now": [],
                    "next_10_working_days": [],
                    "blocked": [],
                    "awaiting_internal_review": [],
                    "awaiting_client_review": [],
                },
                "generated_at": datetime.utcnow().isoformat(),
            }

        deliverable_ids = sorted({self._linked_deliverable_id(s) for s in steps if self._linked_deliverable_id(s)})
        deliverables_by_id = (
            {
                d.id: d
                for d in self.db.scalars(
                    select(Deliverable).where(Deliverable.id.in_(deliverable_ids))
                ).all()
            }
            if deliverable_ids
            else {}
        )
        campaign_ids = {d.campaign_id for d in deliverables_by_id.values() if d.campaign_id}.union({s.campaign_id for s in steps if s.campaign_id})
        campaigns_by_id = {
            c.id: c
            for c in self.db.scalars(
                select(Campaign).where(Campaign.id.in_(sorted(campaign_ids)))
            ).all()
        } if campaign_ids else {}

        buckets = QueueBuckets(now=[], next_10_working_days=[], blocked=[], awaiting_internal_review=[], awaiting_client_review=[])
        for step in steps:
            item = self._item(step, deliverables_by_id, campaigns_by_id, today)
            linked_id = self._linked_deliverable_id(step)
            bucket = self._classify(step, deliverables_by_id.get(linked_id) if linked_id else None, today, window_end)
            getattr(buckets, bucket).append(item)

        for arr in [buckets.now, buckets.blocked, buckets.awaiting_internal_review, buckets.awaiting_client_review, buckets.next_10_working_days]:
            arr.sort(key=lambda x: (-x["derived"]["priority_score"], x["step"]["current_due"] or "9999-12-31"))

        summary = {
            "now": len(buckets.now),
            "next_10_working_days": len(buckets.next_10_working_days),
            "blocked": len(buckets.blocked),
            "awaiting_internal_review": len(buckets.awaiting_internal_review),
            "awaiting_client_review": len(buckets.awaiting_client_review),
        }
        summary["total"] = sum(summary.values())
        return {
            "summary": summary,
            "queues": {
                "now": buckets.now,
                "next_10_working_days": buckets.next_10_working_days,
                "blocked": buckets.blocked,
                "awaiting_internal_review": buckets.awaiting_internal_review,
                "awaiting_client_review": buckets.awaiting_client_review,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _classify(self, step: WorkflowStep, deliverable: Deliverable | None, today: date, window_end: date) -> str:
        if step.current_due and step.current_due <= today:
            return "now"
        if step.waiting_on_type is not None:
            return "blocked"
        if deliverable and deliverable.status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            return "awaiting_internal_review"
        if deliverable and deliverable.status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            return "awaiting_client_review"
        return "next_10_working_days"

    def _item(
        self,
        step: WorkflowStep,
        deliverables_by_id: dict[str, Deliverable],
        campaigns_by_id: dict[str, Campaign],
        today: date,
    ) -> dict:
        linked_id = self._linked_deliverable_id(step)
        deliverable = deliverables_by_id.get(linked_id) if linked_id else None
        campaign = (
            campaigns_by_id.get(step.campaign_id)
            or (campaigns_by_id.get(deliverable.campaign_id) if deliverable and deliverable.campaign_id else None)
        )

        is_overdue = bool(step.current_due and step.current_due < today)
        days_until_due = (step.current_due - today).days if step.current_due else None
        waiting_age_days = (datetime.utcnow() - step.waiting_since).days if step.waiting_since else 0
        priority_score = self._priority_score(step, deliverable, is_overdue, days_until_due, waiting_age_days)

        return {
            "step": {
                "id": step.display_id,
                "name": step.name,
                "step_kind": step.step_kind.value,
                "owner_role": step.owner_role.value,
                "next_owner_user_id": step.next_owner_user_id,
                "current_start": step.current_start.isoformat() if step.current_start else None,
                "current_due": step.current_due.isoformat() if step.current_due else None,
                "waiting_on_type": step.waiting_on_type.value if step.waiting_on_type else None,
                "waiting_on_user_id": step.waiting_on_user_id,
                "blocker_reason": step.blocker_reason,
            },
            "deliverable": {
                "id": deliverable.display_id if deliverable else None,
                "title": deliverable.title if deliverable else None,
                "status": deliverable.status.value if deliverable else None,
            },
            "campaign": {
                "id": campaign.display_id if campaign else None,
                "title": campaign.title if campaign else None,
            },
            "derived": {
                "is_overdue": is_overdue,
                "days_until_due": days_until_due,
                "waiting_age_days": waiting_age_days,
                "priority_score": priority_score,
            },
        }

    @staticmethod
    def _linked_deliverable_id(step: WorkflowStep) -> str | None:
        return step.linked_deliverable_id

    def _priority_score(
        self,
        step: WorkflowStep,
        deliverable: Deliverable | None,
        is_overdue: bool,
        days_until_due: int | None,
        waiting_age_days: int,
    ) -> int:
        score = 0
        if is_overdue:
            score += 100
        if step.waiting_on_type is not None:
            score += 80
        if deliverable and deliverable.status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            score += 70
        if deliverable and deliverable.status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            score += 60
        if days_until_due is not None:
            score += max(0, 20 - days_until_due)
        score += min(max(waiting_age_days, 0), 20)
        return score
