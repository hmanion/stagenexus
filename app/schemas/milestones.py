from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MilestoneCompletionUpdateIn(BaseModel):
    actor_user_id: str
    completion_date_iso: str | None = None


class MilestoneSlaOverrideIn(BaseModel):
    actor_user_id: str
    sla_health: str
    clear_override: bool = False


class MilestoneUpdateIn(BaseModel):
    actor_user_id: str
    owner_user_id: str | None = None
    due_date_iso: str | None = None
