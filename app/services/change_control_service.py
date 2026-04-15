from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    ActivityLog,
    ApprovalStatus,
    RoleName,
    SowChangeApproval,
    SowChangeRequest,
)
from app.services.id_service import PublicIdService


REQUIRED_ROLES = {RoleName.HEAD_OPS, RoleName.HEAD_SALES}


class ChangeControlService:
    def __init__(self, db: Session):
        self.db = db
        self.public_ids = PublicIdService(db)

    def create_request(self, campaign_id: str, requested_by_user_id: str, impact_scope_json: dict) -> SowChangeRequest:
        req = SowChangeRequest(
            display_id=self.public_ids.next_id(SowChangeRequest, "SOW"),
            campaign_id=campaign_id,
            requested_by_user_id=requested_by_user_id,
            impact_scope_json=impact_scope_json,
            status="pending",
        )
        self.db.add(req)
        self.db.flush()

        for role in REQUIRED_ROLES:
            self.db.add(
                SowChangeApproval(
                    display_id=self.public_ids.next_id(SowChangeApproval, "SOWA"),
                    sow_change_request_id=req.id,
                    approver_role=role,
                    status=ApprovalStatus.PENDING,
                )
            )

        self._log(requested_by_user_id, "sow_change_request", req.id, "created")
        return req

    def apply_approval(self, request_id: str, approver_user_id: str, approver_role: RoleName, decision: str) -> SowChangeRequest:
        req = self.db.get(SowChangeRequest, request_id) or self.db.scalar(
            select(SowChangeRequest).where(SowChangeRequest.display_id == request_id)
        )
        if not req:
            raise ValueError("SOW change request not found")

        if approver_role not in REQUIRED_ROLES:
            raise ValueError("Invalid approver role")

        record = self.db.scalar(
            select(SowChangeApproval).where(
                SowChangeApproval.sow_change_request_id == req.id,
                SowChangeApproval.approver_role == approver_role,
            )
        )
        if not record:
            raise ValueError(
                "Approval record not found for this request and role; this request may be missing seeded approval rows"
            )

        normalized = decision.lower().strip()
        if normalized not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")

        record.approver_user_id = approver_user_id
        record.status = ApprovalStatus.APPROVED if normalized == "approved" else ApprovalStatus.REJECTED
        record.decided_at = datetime.utcnow()

        approvals = self.db.scalars(
            select(SowChangeApproval).where(SowChangeApproval.sow_change_request_id == req.id)
        ).all()

        if any(a.status == ApprovalStatus.REJECTED for a in approvals):
            req.status = "rejected"
        elif all(a.status == ApprovalStatus.APPROVED for a in approvals):
            req.status = "activated"
            req.activated_at = datetime.utcnow()

        self._log(approver_user_id, "sow_change_request", req.id, f"{normalized}_by_{approver_role.value}")
        return req

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
