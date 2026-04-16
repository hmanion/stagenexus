from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.domain import RoleName, SeniorityLevel, TeamName


def can_actor_approve_scope(db: Session, actor: Any) -> bool:
    from app.api.core_routes import _actor_has_control_permission

    if _actor_has_control_permission(
        db,
        actor,
        "approve_scope",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        return True
    return actor.seniority == SeniorityLevel.LEADERSHIP and actor.primary_team == TeamName.CLIENT_SERVICES


def can_actor_generate_campaigns(db: Session, actor: Any) -> bool:
    from app.api.core_routes import _actor_has_control_permission

    if _actor_has_control_permission(
        db,
        actor,
        "generate_latest_campaigns",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        return True
    return actor.seniority == SeniorityLevel.LEADERSHIP and actor.primary_team == TeamName.CLIENT_SERVICES
