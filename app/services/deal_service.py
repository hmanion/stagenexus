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
    Scope,
    ScopeAttachment,
    ScopeProductLine,
    ScopeStatus,
    PublicationName,
)
from app.services.id_service import PublicIdService
from app.schemas.scopes import ScopeCreateIn, OpsApproveIn


class ScopeService:
    def __init__(self, db: Session):
        self.db = db
        self.public_ids = PublicIdService(db)

    def create_scope(self, payload: ScopeCreateIn) -> Scope:
        client = self.db.scalar(select(Client).where(Client.name == payload.client_name))
        if client is None:
            client = Client(name=payload.client_name)
            self.db.add(client)
            self.db.flush()
        try:
            brand_publication = PublicationName(payload.brand_publication)
        except ValueError as exc:
            raise ValueError(f"Invalid brand_publication: {payload.brand_publication}") from exc

        scope = Scope(
            display_id=self.public_ids.next_scope_id(Scope, client.name, submitted_on=date.today()),
            client_id=client.id,
            am_user_id=payload.am_user_id,
            brand_publication=brand_publication,
            sow_start_date=payload.sow_start_date,
            sow_end_date=payload.sow_end_date,
            icp=payload.icp,
            campaign_objective=payload.campaign_objective,
            messaging_positioning=payload.messaging_positioning,
            commercial_notes=payload.commercial_notes,
            status=ScopeStatus.DRAFT,
        )
        self.db.add(scope)
        self.db.flush()

        for line in payload.product_lines:
            try:
                product_type = CampaignType(line.product_type)
            except ValueError as exc:
                raise ValueError(f"Invalid product_type: {line.product_type}") from exc
            self.db.add(
                ScopeProductLine(
                    scope_id=scope.id,
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
                ScopeAttachment(
                    scope_id=scope.id,
                    file_name=attachment.file_name,
                    storage_key=attachment.storage_key,
                )
            )

        self._log(scope.am_user_id, "scope", scope.id, "scope_created")
        return scope

    def submit_scope(self, scope: Scope) -> Scope:
        client = self.db.get(Client, scope.client_id)
        submitted_year = date.today().year % 100
        expected = re.compile(rf"^[A-Z]{{4}}-{submitted_year:02d}-\d{{3}}$")
        if client and (not scope.display_id or not expected.match(scope.display_id)):
            scope.display_id = self.public_ids.next_scope_id(Scope, client.name, submitted_on=date.today())
        scope.status = ScopeStatus.SUBMITTED
        self._log(scope.am_user_id, "scope", scope.id, "scope_submitted")
        return scope

    def ops_approve(self, scope: Scope, payload: OpsApproveIn) -> Scope:
        scope.status = ScopeStatus.OPS_APPROVED
        scope.assigned_cm_user_id = payload.cm_user_id
        scope.assigned_cc_user_id = payload.cc_user_id
        scope.assigned_ccs_user_id = payload.ccs_user_id
        scope.readiness_passed = self._readiness_gate_passed(scope)
        scope.status = ScopeStatus.READINESS_PASSED if scope.readiness_passed else ScopeStatus.READINESS_FAILED

        # Assignment placeholders at scope-level via campaign id = "pending" marker in activity.
        self._log(payload.head_ops_user_id, "scope", scope.id, "ops_approved")
        self._log(payload.head_ops_user_id, "scope", scope.id, "staffing_assigned", {
            "cm_user_id": payload.cm_user_id,
            "cc_user_id": payload.cc_user_id,
            "ccs_user_id": payload.ccs_user_id,
        })
        return scope

    def _readiness_gate_passed(self, scope: Scope) -> bool:
        # Operational readiness gate.
        if not scope.sow_start_date or not scope.sow_end_date:
            return False
        if not scope.icp:
            return False
        if not scope.campaign_objective or not scope.messaging_positioning:
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
