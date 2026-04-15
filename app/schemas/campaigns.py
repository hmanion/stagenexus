from __future__ import annotations

from pydantic import BaseModel


class CampaignOut(BaseModel):
    id: str
    type: str
    tier: str
    title: str


class CampaignAssignmentsUpdateIn(BaseModel):
    actor_user_id: str
    am_user_id: str | None = None
    cm_user_id: str | None = None
    cc_user_id: str | None = None
    ccs_user_id: str | None = None
    dn_user_id: str | None = None
    mm_user_id: str | None = None
    cascade_owner_updates: bool = False


class CampaignStatusUpdateIn(BaseModel):
    actor_user_id: str
    status: str


class CampaignDatesUpdateIn(BaseModel):
    actor_user_id: str
    planned_start_iso: str | None = None
    planned_end_iso: str | None = None
