from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.domain import Deal, RoleName
from app.services.authz_service import AuthzService


def get_actor(db: Session, actor_user_id: str) -> Any:
    return AuthzService(db).actor(actor_user_id)


def get_deal_or_404(db: Session, deal_id: str, *, detail: str = "scope not found") -> Deal:
    from app.api.core_routes import _resolve_by_identifier

    deal = _resolve_by_identifier(db, Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail=detail)
    return deal


def require_deal_owner_or_roles(
    db: Session,
    actor_user_id: str,
    deal: Deal,
    allowed_roles: set[RoleName],
) -> Any:
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_deal_owner_or_roles(actor, deal, allowed_roles)
    return actor
