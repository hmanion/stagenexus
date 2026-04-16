from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.core_routes import _resolve_by_identifier, router as core_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.deals import router as deals_router
from app.db.session import get_db
from app.models.domain import Campaign, RoleName
from app.schemas.deals import SowChangeCreateIn
from app.services.authz_service import AuthzService
from app.services.change_control_service import ChangeControlService

# Compatibility export for older imports that referenced `app.api.routes.router`.
router = APIRouter()
router.include_router(deals_router)
router.include_router(campaigns_router)
router.include_router(core_router)


def create_sow_change_request(
    campaign_id: str,
    payload: SowChangeCreateIn,
    actor_user_id: str,
    db: Session = Depends(get_db),
):
    """
    Compatibility wrapper for code/tests that still import this route from
    `app.api.routes` after the route split.
    """
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_any(actor, {RoleName.CM, RoleName.AM, RoleName.HEAD_OPS, RoleName.ADMIN})
    if payload.requested_by_user_id != actor_user_id and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor must match requested_by_user_id unless admin")

    req = ChangeControlService(db).create_request(
        campaign_id=campaign.id,
        requested_by_user_id=payload.requested_by_user_id,
        impact_scope_json=payload.impact_scope_json,
    )
    db.commit()
    return {"id": req.display_id, "status": req.status}


__all__ = [
    "AuthzService",
    "ChangeControlService",
    "_resolve_by_identifier",
    "create_sow_change_request",
    "router",
]
