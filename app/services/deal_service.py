from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    ActivityLog,
    CampaignType,
    Client,
    ClientContact,
    Deal,
    DealAttachment,
    DealProductLine,
    DealStatus,
    PublicationName,
)
from app.services.id_service import PublicIdService
from app.schemas.deals import DealCreateIn, OpsApproveIn


class DealService:
    def __init__(self, db: Session):
        self.db = db
        self.public_ids = PublicIdService(db)

    def create_deal(self, payload: DealCreateIn) -> Deal:
        client = self.db.scalar(select(Client).where(Client.name == payload.client_name))
        if client is None:
            client = Client(name=payload.client_name)
            self.db.add(client)
            self.db.flush()
        try:
            brand_publication = PublicationName(payload.brand_publication)
        except ValueError as exc:
            raise ValueError(f"Invalid brand_publication: {payload.brand_publication}") from exc

        deal = Deal(
            display_id=self.public_ids.next_deal_id(Deal, client.name, submitted_on=date.today()),
            client_id=client.id,
            am_user_id=payload.am_user_id,
            brand_publication=brand_publication,
            sow_start_date=payload.sow_start_date,
            sow_end_date=payload.sow_end_date,
            icp=payload.icp,
            campaign_objective=payload.campaign_objective,
            messaging_positioning=payload.messaging_positioning,
            commercial_notes=payload.commercial_notes,
            status=DealStatus.DRAFT,
        )
        self.db.add(deal)
        self.db.flush()

        for line in payload.product_lines:
            try:
                product_type = CampaignType(line.product_type)
            except ValueError as exc:
                raise ValueError(f"Invalid product_type: {line.product_type}") from exc
            self.db.add(
                DealProductLine(
                    deal_id=deal.id,
                    product_type=product_type,
                    tier=line.tier,
                    options_json={
                        **line.options_json,
                        "demand_module_mode": line.demand_module_mode,
                        "reach_level": line.reach_level,
                        "capture_level": line.capture_level,
                        "lead_volume": line.lead_volume,
                    },
                )
            )
        for contact in payload.client_contacts:
            self.db.add(
                ClientContact(
                    client_id=client.id,
                    name=contact.name,
                    email=contact.email,
                    title=contact.title,
                )
            )
        for attachment in payload.attachments:
            self.db.add(
                DealAttachment(
                    deal_id=deal.id,
                    file_name=attachment.file_name,
                    storage_key=attachment.storage_key,
                )
            )

        self._log(deal.am_user_id, "deal", deal.id, "deal_created")
        return deal

    def submit_deal(self, deal: Deal) -> Deal:
        client = self.db.get(Client, deal.client_id)
        submitted_year = date.today().year % 100
        expected = re.compile(rf"^[A-Z]{{4}}-{submitted_year:02d}-\d{{3}}$")
        if client and (not deal.display_id or not expected.match(deal.display_id)):
            deal.display_id = self.public_ids.next_deal_id(Deal, client.name, submitted_on=date.today())
        deal.status = DealStatus.SUBMITTED
        self._log(deal.am_user_id, "deal", deal.id, "deal_submitted")
        return deal

    def ops_approve(self, deal: Deal, payload: OpsApproveIn) -> Deal:
        deal.status = DealStatus.OPS_APPROVED
        deal.assigned_cm_user_id = payload.cm_user_id
        deal.assigned_cc_user_id = payload.cc_user_id
        deal.assigned_ccs_user_id = payload.ccs_user_id
        deal.readiness_passed = self._readiness_gate_passed(deal)
        deal.status = DealStatus.READINESS_PASSED if deal.readiness_passed else DealStatus.READINESS_FAILED

        # Assignment placeholders at deal-level via campaign id = "pending" marker in activity.
        self._log(payload.head_ops_user_id, "deal", deal.id, "ops_approved")
        self._log(payload.head_ops_user_id, "deal", deal.id, "staffing_assigned", {
            "cm_user_id": payload.cm_user_id,
            "cc_user_id": payload.cc_user_id,
            "ccs_user_id": payload.ccs_user_id,
        })
        return deal

    def _readiness_gate_passed(self, deal: Deal) -> bool:
        # Operational readiness gate.
        if not deal.sow_start_date or not deal.sow_end_date:
            return False
        if not deal.icp:
            return False
        if not deal.campaign_objective or not deal.messaging_positioning:
            return False
        return True

    def _log(self, actor_user_id: str, entity_type: str, entity_id: str, action: str, meta: dict | None = None) -> None:
        self.db.add(
            ActivityLog(
                display_id=self.public_ids.next_id(ActivityLog, "ACT"),
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                meta_json=meta or {},
            )
        )
