from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class DealProductLineIn(BaseModel):
    product_type: str
    tier: str
    options_json: dict[str, Any] = Field(default_factory=dict)
    demand_module_mode: str | None = None
    reach_level: str | None = None
    capture_level: str | None = None
    lead_volume: int | None = None


class DealClientContactIn(BaseModel):
    name: str
    email: str
    title: str | None = None


class DealAttachmentIn(BaseModel):
    file_name: str
    storage_key: str


class DealCreateIn(BaseModel):
    client_name: str
    brand_publication: str
    am_user_id: str
    sow_start_date: date | None = None
    sow_end_date: date | None = None
    icp: str | None = None
    campaign_objective: str | None = None
    messaging_positioning: str | None = None
    commercial_notes: str | None = None
    client_contacts: list[DealClientContactIn] = Field(default_factory=list)
    attachments: list[DealAttachmentIn] = Field(default_factory=list)
    product_lines: list[DealProductLineIn]


class DealOut(BaseModel):
    id: str
    status: str
    client_name: str | None = None
    brand_publication: str | None = None


class OpsApproveIn(BaseModel):
    head_ops_user_id: str
    cm_user_id: str
    cc_user_id: str
    ccs_user_id: str | None = None


class SowChangeCreateIn(BaseModel):
    requested_by_user_id: str
    impact_scope_json: dict[str, Any] = Field(default_factory=dict)


class SowChangeApproveIn(BaseModel):
    approver_user_id: str
    approver_role: str
    decision: str
