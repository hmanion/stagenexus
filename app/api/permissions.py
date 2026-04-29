from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.domain import RoleName, SeniorityLevel, TeamName
from app.services.authz_service import AuthzService


def can_actor_approve_scope(db: Session, actor: Any) -> bool:
    if AuthzService(db).has_control_permission(
        actor,
        "approve_scope",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        return True
    return actor.seniority == SeniorityLevel.LEADERSHIP and actor.primary_team == TeamName.CLIENT_SERVICES


def can_actor_generate_campaigns(db: Session, actor: Any) -> bool:
    if AuthzService(db).has_control_permission(
        actor,
        "generate_latest_campaigns",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        return True
    return actor.seniority == SeniorityLevel.LEADERSHIP and actor.primary_team == TeamName.CLIENT_SERVICES
