from __future__ import annotations

from pydantic import BaseModel


class StepCompleteIn(BaseModel):
    actor_user_id: str


class StepOverrideDueIn(BaseModel):
    actor_user_id: str
    current_due_iso: str
    reason_code: str


class StepManageIn(BaseModel):
    actor_user_id: str
    status: str | None = None
    next_owner_user_id: str | None = None
    waiting_on_user_id: str | None = None
    blocker_reason: str | None = None
    current_start_iso: str | None = None
    current_due_iso: str | None = None
    planned_work_date_iso: str | None = None
    completion_date_iso: str | None = None
