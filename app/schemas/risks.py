from __future__ import annotations

from pydantic import BaseModel


class ManualRiskCreateIn(BaseModel):
    actor_user_id: str
    campaign_id: str
    severity: str
    details: str
    mitigation_owner_user_id: str | None = None
    mitigation_due: str | None = None


class ManualRiskUpdateIn(BaseModel):
    actor_user_id: str
    is_open: bool | None = None
    severity: str | None = None
    details: str | None = None
    mitigation_owner_user_id: str | None = None
    mitigation_due: str | None = None


class EscalationResolveIn(BaseModel):
    actor_user_id: str
