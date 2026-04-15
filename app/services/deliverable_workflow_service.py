from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    ActivityLog,
    Campaign,
    Deliverable,
    DeliverableStatus,
    Review,
    ReviewRoundEvent,
    ReviewRoundEventType,
    ReviewWindow,
    ReviewWindowStatus,
    ReviewWindowType,
    RoleName,
    TemplateVersion,
    WaitingOnType,
    WorkflowStep,
)
from app.services.calendar_service import build_default_working_calendar
from app.services.id_service import PublicIdService
from app.services.ops_defaults_service import OpsDefaultsService


@dataclass(frozen=True)
class TransitionRule:
    from_status: DeliverableStatus
    to_status: DeliverableStatus
    allowed_roles: set[RoleName]


RULES = {
    (DeliverableStatus.PLANNED, DeliverableStatus.IN_PROGRESS): {RoleName.CM, RoleName.CC, RoleName.CCS},
    (DeliverableStatus.IN_PROGRESS, DeliverableStatus.AWAITING_INTERNAL_REVIEW): {RoleName.CM, RoleName.CC, RoleName.CCS},
    (DeliverableStatus.AWAITING_INTERNAL_REVIEW, DeliverableStatus.INTERNAL_REVIEW_COMPLETE): {RoleName.CM, RoleName.HEAD_OPS},
    (DeliverableStatus.INTERNAL_REVIEW_COMPLETE, DeliverableStatus.AWAITING_CLIENT_REVIEW): {RoleName.AM, RoleName.CM},
    (DeliverableStatus.AWAITING_CLIENT_REVIEW, DeliverableStatus.CLIENT_CHANGES_REQUESTED): {RoleName.AM, RoleName.CM},
    (DeliverableStatus.AWAITING_CLIENT_REVIEW, DeliverableStatus.APPROVED): {RoleName.AM, RoleName.CM},
    (DeliverableStatus.CLIENT_CHANGES_REQUESTED, DeliverableStatus.IN_PROGRESS): {RoleName.CM, RoleName.CC, RoleName.CCS},
    (DeliverableStatus.APPROVED, DeliverableStatus.READY_TO_PUBLISH): {RoleName.CM, RoleName.CC},
    (DeliverableStatus.READY_TO_PUBLISH, DeliverableStatus.SCHEDULED_OR_PUBLISHED): {RoleName.CM, RoleName.AM},
    (DeliverableStatus.SCHEDULED_OR_PUBLISHED, DeliverableStatus.COMPLETE): {RoleName.CM, RoleName.HEAD_OPS},
}


class DeliverableWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.public_ids = PublicIdService(db)
        self.calendar = build_default_working_calendar()
        self.ops_defaults = OpsDefaultsService(db).get()

    def transition(
        self,
        deliverable: Deliverable,
        to_status: DeliverableStatus,
        actor_user_id: str,
        actor_roles: set[RoleName],
        comment: str | None = None,
    ) -> Deliverable:
        current = deliverable.status
        if current == to_status:
            return deliverable

        allowed = RULES.get((current, to_status))
        if not allowed:
            raise HTTPException(status_code=400, detail=f"invalid status transition: {current.value} -> {to_status.value}")

        if RoleName.ADMIN not in actor_roles and not actor_roles.intersection(allowed):
            raise HTTPException(status_code=403, detail="actor role not allowed for this transition")

        if to_status == DeliverableStatus.CLIENT_CHANGES_REQUESTED and not (comment or "").strip():
            raise HTTPException(status_code=400, detail="comment is required when client changes are requested")

        now = datetime.utcnow()
        deliverable.status = to_status
        self._apply_review_timestamps(deliverable, to_status, now)
        self._apply_waiting_state_to_open_steps(deliverable.id, to_status, now)
        self._apply_review_windows_and_rounds(deliverable=deliverable, to_status=to_status, actor_user_id=actor_user_id, now=now)

        if to_status == DeliverableStatus.READY_TO_PUBLISH:
            deliverable.ready_to_publish_by_user_id = actor_user_id
            deliverable.ready_to_publish_at = now
        if to_status == DeliverableStatus.SCHEDULED_OR_PUBLISHED:
            deliverable.scheduled_or_published_at = now
        if to_status == DeliverableStatus.COMPLETE:
            deliverable.actual_done = now

        self._record_review_if_relevant(deliverable, to_status, actor_user_id, comment)
        self.db.add(
            ActivityLog(
                display_id=self.public_ids.next_id(ActivityLog, "ACT"),
                actor_user_id=actor_user_id,
                entity_type="deliverable",
                entity_id=deliverable.id,
                action=f"status:{current.value}->{to_status.value}",
                meta_json={"comment": comment or ""},
            )
            )
        return deliverable

    def increment_round(
        self,
        deliverable: Deliverable,
        round_type: str,
        actor_user_id: str,
        note: str,
    ) -> dict:
        normalized = (round_type or "").strip().lower()
        if not (note or "").strip():
            raise HTTPException(status_code=400, detail="note is required")
        now = datetime.utcnow()
        if normalized == "internal":
            deliverable.internal_review_rounds += 1
            round_no = int(deliverable.internal_review_rounds)
            window_type = ReviewWindowType.INTERNAL_REVIEW
            event_type = ReviewRoundEventType.INTERNAL_ROUND_INCREMENTED
        elif normalized == "client":
            deliverable.client_review_rounds += 1
            round_no = int(deliverable.client_review_rounds)
            window_type = ReviewWindowType.CLIENT_REVIEW
            event_type = ReviewRoundEventType.CLIENT_ROUND_INCREMENTED
        elif normalized == "amends":
            deliverable.amend_rounds += 1
            round_no = int(deliverable.amend_rounds)
            window_type = ReviewWindowType.AMENDS
            event_type = ReviewRoundEventType.AMEND_ROUND_INCREMENTED
        else:
            raise HTTPException(status_code=400, detail="round_type must be internal|client|amends")

        self._record_round_event(deliverable, event_type, round_no, actor_user_id, note, source="manual", at=now)
        self._open_review_window(deliverable, window_type, round_no, actor_user_id, now, reopen_if_closed=True)
        self.db.add(
            ActivityLog(
                display_id=self.public_ids.next_id(ActivityLog, "ACT"),
                actor_user_id=actor_user_id,
                entity_type="deliverable",
                entity_id=deliverable.id,
                action="review_round_incremented",
                meta_json={
                    "deliverable_id": deliverable.display_id,
                    "round_type": normalized,
                    "round_number": round_no,
                    "note": note,
                    "source": "manual",
                },
            )
        )
        return {
            "deliverable_id": deliverable.display_id,
            "round_type": normalized,
            "round_number": round_no,
        }

    def list_windows(self, deliverable: Deliverable) -> list[ReviewWindow]:
        return self.db.scalars(
            select(ReviewWindow)
            .where(ReviewWindow.deliverable_id == deliverable.id)
            .order_by(ReviewWindow.window_start.desc(), ReviewWindow.created_at.desc())
        ).all()

    def _apply_review_timestamps(self, deliverable: Deliverable, to_status: DeliverableStatus, now: datetime) -> None:
        if to_status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            deliverable.awaiting_internal_review_since = now
        elif to_status == DeliverableStatus.INTERNAL_REVIEW_COMPLETE:
            deliverable.awaiting_internal_review_since = None

        if to_status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            deliverable.awaiting_client_review_since = now
        elif to_status in {DeliverableStatus.CLIENT_CHANGES_REQUESTED, DeliverableStatus.APPROVED}:
            deliverable.awaiting_client_review_since = None
            if to_status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
                deliverable.client_changes_requested_at = now
            if to_status == DeliverableStatus.APPROVED:
                deliverable.approved_at = now

    def _apply_review_windows_and_rounds(
        self,
        deliverable: Deliverable,
        to_status: DeliverableStatus,
        actor_user_id: str,
        now: datetime,
    ) -> None:
        if to_status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            deliverable.internal_review_rounds += 1
            round_no = int(deliverable.internal_review_rounds)
            self._record_round_event(
                deliverable,
                ReviewRoundEventType.INTERNAL_ROUND_INCREMENTED,
                round_no,
                actor_user_id,
                note="Entered awaiting internal review",
                source="auto",
                at=now,
            )
            self._open_review_window(deliverable, ReviewWindowType.INTERNAL_REVIEW, round_no, actor_user_id, now)
            return

        if to_status == DeliverableStatus.INTERNAL_REVIEW_COMPLETE:
            self._complete_open_window(deliverable.id, ReviewWindowType.INTERNAL_REVIEW, now)
            return

        if to_status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            self._complete_open_window(deliverable.id, ReviewWindowType.AMENDS, now)
            deliverable.client_review_rounds += 1
            round_no = int(deliverable.client_review_rounds)
            self._record_round_event(
                deliverable,
                ReviewRoundEventType.CLIENT_ROUND_INCREMENTED,
                round_no,
                actor_user_id,
                note="Entered awaiting client review",
                source="auto",
                at=now,
            )
            self._open_review_window(deliverable, ReviewWindowType.CLIENT_REVIEW, round_no, actor_user_id, now)
            return

        if to_status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
            self._complete_open_window(deliverable.id, ReviewWindowType.CLIENT_REVIEW, now)
            deliverable.amend_rounds += 1
            round_no = int(deliverable.amend_rounds)
            self._record_round_event(
                deliverable,
                ReviewRoundEventType.AMEND_ROUND_INCREMENTED,
                round_no,
                actor_user_id,
                note="Client changes requested",
                source="auto",
                at=now,
            )
            self._open_review_window(deliverable, ReviewWindowType.AMENDS, round_no, actor_user_id, now)
            return

        if to_status in {DeliverableStatus.APPROVED, DeliverableStatus.READY_TO_PUBLISH, DeliverableStatus.SCHEDULED_OR_PUBLISHED, DeliverableStatus.COMPLETE}:
            self._complete_open_window(deliverable.id, ReviewWindowType.CLIENT_REVIEW, now)
            self._complete_open_window(deliverable.id, ReviewWindowType.AMENDS, now)

    def _window_days_for(self, deliverable: Deliverable, window_type: ReviewWindowType) -> int:
        key = "internal" if window_type == ReviewWindowType.INTERNAL_REVIEW else ("client" if window_type == ReviewWindowType.CLIENT_REVIEW else "amends")
        defaults = (self.ops_defaults.get("review_windows_working_days") or {})
        default_days = int(defaults.get(key, 2))
        campaign = self.db.get(Campaign, deliverable.campaign_id) if deliverable.campaign_id else None
        if campaign:
            tpl = self.db.get(TemplateVersion, campaign.template_version_id)
            if tpl:
                by_deliv = ((tpl.workflow_json or {}).get("review_windows_working_days_by_deliverable") or {}).get(deliverable.deliverable_type.value, {})
                if key in by_deliv:
                    return max(int(by_deliv[key]), 1)
                tpl_defaults = (tpl.workflow_json or {}).get("review_windows_working_days") or {}
                if key in tpl_defaults:
                    return max(int(tpl_defaults[key]), 1)
        return max(default_days, 1)

    def _open_review_window(
        self,
        deliverable: Deliverable,
        window_type: ReviewWindowType,
        round_number: int,
        actor_user_id: str,
        now: datetime,
        reopen_if_closed: bool = False,
    ) -> None:
        existing = self.db.scalar(
            select(ReviewWindow).where(
                ReviewWindow.deliverable_id == deliverable.id,
                ReviewWindow.window_type == window_type,
                ReviewWindow.round_number == round_number,
            )
        )
        if existing and existing.status == ReviewWindowStatus.OPEN:
            return
        if existing and not reopen_if_closed:
            return
        start = now.date()
        due = self.calendar.add_working_days(start, self._window_days_for(deliverable, window_type))
        if existing:
            existing.window_start = start
            existing.window_due = due
            existing.completed_at = None
            existing.status = ReviewWindowStatus.OPEN
            existing.created_by_user_id = actor_user_id
            return
        self.db.add(
            ReviewWindow(
                display_id=self.public_ids.next_id(ReviewWindow, "RWIN"),
                deliverable_id=deliverable.id,
                window_type=window_type,
                window_start=start,
                window_due=due,
                status=ReviewWindowStatus.OPEN,
                round_number=round_number,
                created_by_user_id=actor_user_id,
            )
        )

    def _complete_open_window(self, deliverable_id: str, window_type: ReviewWindowType, now: datetime) -> None:
        rows = self.db.scalars(
            select(ReviewWindow).where(
                ReviewWindow.deliverable_id == deliverable_id,
                ReviewWindow.window_type == window_type,
                ReviewWindow.status == ReviewWindowStatus.OPEN,
            )
        ).all()
        for row in rows:
            row.status = ReviewWindowStatus.COMPLETE
            row.completed_at = now

    def _record_round_event(
        self,
        deliverable: Deliverable,
        event_type: ReviewRoundEventType,
        round_number: int,
        actor_user_id: str,
        note: str,
        source: str,
        at: datetime,
    ) -> None:
        self.db.add(
            ReviewRoundEvent(
                display_id=self.public_ids.next_id(ReviewRoundEvent, "RREV"),
                deliverable_id=deliverable.id,
                event_type=event_type,
                round_number=round_number,
                event_at=at,
                actor_user_id=actor_user_id,
                note=note,
                source=source,
            )
        )

    def _apply_waiting_state_to_open_steps(self, deliverable_id: str, to_status: DeliverableStatus, now: datetime) -> None:
        open_steps = self.db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.linked_deliverable_id == deliverable_id,
                WorkflowStep.actual_done.is_(None),
            )
        ).all()
        if not open_steps:
            return

        if to_status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            for step in open_steps:
                step.waiting_on_type = WaitingOnType.INTERNAL
                step.waiting_since = now
                step.blocker_reason = "Awaiting internal review"
            return

        if to_status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            for step in open_steps:
                step.waiting_on_type = WaitingOnType.CLIENT
                step.waiting_since = now
                step.blocker_reason = "Awaiting client review"
            return

        if to_status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
            for step in open_steps:
                step.waiting_on_type = WaitingOnType.INTERNAL
                step.waiting_since = now
                step.blocker_reason = "Client changes requested"
            return

        # Resumed flow / approved / publish / complete clears review-based waiting.
        for step in open_steps:
            if step.waiting_on_type in {WaitingOnType.INTERNAL, WaitingOnType.CLIENT}:
                step.waiting_on_type = None
                step.waiting_since = None
                step.blocker_reason = None

    def _record_review_if_relevant(
        self,
        deliverable: Deliverable,
        status: DeliverableStatus,
        actor_user_id: str,
        comment: str | None,
    ) -> None:
        if status in {DeliverableStatus.AWAITING_INTERNAL_REVIEW, DeliverableStatus.INTERNAL_REVIEW_COMPLETE}:
            self.db.add(
                Review(
                    display_id=self.public_ids.next_id(Review, "REV"),
                    deliverable_id=deliverable.id,
                    review_type="internal",
                    status="complete" if status == DeliverableStatus.INTERNAL_REVIEW_COMPLETE else "pending",
                    reviewer_user_id=actor_user_id,
                    comments=comment,
                )
            )
        elif status in {DeliverableStatus.AWAITING_CLIENT_REVIEW, DeliverableStatus.CLIENT_CHANGES_REQUESTED, DeliverableStatus.APPROVED}:
            review_status = "pending"
            if status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
                review_status = "changes_requested"
            elif status == DeliverableStatus.APPROVED:
                review_status = "approved"
            self.db.add(
                Review(
                    display_id=self.public_ids.next_id(Review, "REV"),
                    deliverable_id=deliverable.id,
                    review_type="client",
                    status=review_status,
                    reviewer_user_id=actor_user_id,
                    comments=comment,
                )
            )
