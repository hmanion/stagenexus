from __future__ import annotations

from pydantic import BaseModel


class DeliverableTransitionIn(BaseModel):
    actor_user_id: str
    to_status: str
    comment: str | None = None


class ReviewRoundIncrementIn(BaseModel):
    actor_user_id: str
    round_type: str
    note: str


class DeliverableDueUpdateIn(BaseModel):
    actor_user_id: str
    current_due_iso: str
    reason_code: str


class DeliverableDatesUpdateIn(BaseModel):
    actor_user_id: str
    current_start_iso: str | None = None
    current_due_iso: str | None = None
    reason_code: str | None = None


class DeliverableStageUpdateIn(BaseModel):
    actor_user_id: str
    stage: str


class DeliverableOwnerUpdateIn(BaseModel):
    actor_user_id: str
    owner_user_id: str | None = None


class CapacityOverrideRequestIn(BaseModel):
    actor_user_id: str
    reason: str


class CapacityOverrideDecisionIn(BaseModel):
    actor_user_id: str
    approve: bool
    reason: str | None = None
