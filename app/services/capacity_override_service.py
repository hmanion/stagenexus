from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.domain import ActivityLog, CapacityLedger
from app.services.id_service import PublicIdService


class CapacityOverrideService:
    def __init__(self, db: Session):
        self.db = db
        self.public_ids = PublicIdService(db)

    def request_override(self, row: CapacityLedger, actor_user_id: str, reason: str) -> CapacityLedger:
        if row.planned_hours <= row.capacity_hours:
            raise HTTPException(status_code=400, detail="override not needed: row is not over capacity")

        row.override_requested = True
        row.override_requested_by_user_id = actor_user_id
        row.override_requested_at = datetime.utcnow()
        row.override_reason = reason
        row.override_approved = False
        row.override_approved_by_user_id = None
        row.override_decided_at = None

        self._log(actor_user_id, row, "override_requested", reason)
        return row

    def decide_override(self, row: CapacityLedger, actor_user_id: str, approve: bool, reason: str | None) -> CapacityLedger:
        if not row.override_requested:
            raise HTTPException(status_code=400, detail="no pending override request")

        row.override_approved = bool(approve)
        row.override_approved_by_user_id = actor_user_id if approve else None
        row.override_decided_at = datetime.utcnow()
        if reason:
            row.override_reason = reason

        self._log(actor_user_id, row, "override_approved" if approve else "override_rejected", reason)
        return row

    def _log(self, actor_user_id: str, row: CapacityLedger, action: str, reason: str | None) -> None:
        self.db.add(
            ActivityLog(
                display_id=self.public_ids.next_id(ActivityLog, "ACT"),
                actor_user_id=actor_user_id,
                entity_type="capacity_ledger",
                entity_id=row.id,
                action=action,
                meta_json={"reason": reason or "", "display_id": row.display_id},
            )
        )
