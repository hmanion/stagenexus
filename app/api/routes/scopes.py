"""Compatibility shim for Scope routes.

Scope endpoints are currently defined in `deals.py` during migration.
"""

from app.api.deps import get_scope_or_404
from app.api.deps import get_actor
from app.api.permissions import can_actor_generate_campaigns
from app.api.routes import deals
from app.api.routes.deals import AuthzService, router


def _with_scope_route_shim(func, *args, **kwargs):
    originals = {
        "AuthzService": deals.AuthzService,
        "can_actor_generate_campaigns": deals.can_actor_generate_campaigns,
        "get_actor": deals.get_actor,
        "get_scope_or_404": deals.get_scope_or_404,
    }
    deals.AuthzService = AuthzService
    deals.can_actor_generate_campaigns = can_actor_generate_campaigns
    deals.get_actor = get_actor
    deals.get_scope_or_404 = get_scope_or_404
    try:
        return func(*args, **kwargs)
    finally:
        deals.AuthzService = originals["AuthzService"]
        deals.can_actor_generate_campaigns = originals["can_actor_generate_campaigns"]
        deals.get_actor = originals["get_actor"]
        deals.get_scope_or_404 = originals["get_scope_or_404"]


def generate_campaigns(scope_id: str, actor_user_id: str, db):
    return _with_scope_route_shim(deals.generate_campaigns, scope_id, actor_user_id=actor_user_id, db=db)


def update_scope_content(scope_id: str, payload, db):
    return _with_scope_route_shim(deals.update_scope_content, scope_id, payload, db=db)


def update_scope_timeframe(scope_id: str, payload, db):
    return _with_scope_route_shim(deals.update_scope_timeframe, scope_id, payload, db=db)


__all__ = [
    "AuthzService",
    "can_actor_generate_campaigns",
    "generate_campaigns",
    "get_actor",
    "get_scope_or_404",
    "router",
    "update_scope_content",
    "update_scope_timeframe",
]
