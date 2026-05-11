from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.identifiers import resolve_by_identifier
from app.models.domain import Scope, RoleName
from app.services.authz_service import AuthzService


def get_actor(db: Session, actor_user_id: str) -> Any:
    return AuthzService(db).actor(actor_user_id)


def get_scope_or_404(db: Session, scope_id: str, *, detail: str = "scope not found") -> Scope:
    scope = resolve_by_identifier(db, Scope, scope_id)
    if not scope:
        raise HTTPException(status_code=404, detail=detail)
    return scope


def require_scope_owner_or_roles(
    db: Session,
    actor_user_id: str,
    scope: Scope,
    allowed_roles: set[RoleName],
) -> Any:
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    authz.require_scope_owner_or_roles(actor, scope, allowed_roles)
    return actor
