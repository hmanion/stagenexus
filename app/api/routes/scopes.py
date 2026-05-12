"""Compatibility shim for Scope routes.

Scope endpoints are currently defined in `deals.py` during migration.
"""

from app.api.deps import get_scope_or_404
from app.api.routes import deals
from app.api.routes.deals import router


def generate_campaigns(scope_id: str, actor_user_id: str, db):
    original = deals.get_scope_or_404
    deals.get_scope_or_404 = get_scope_or_404
    try:
        return deals.generate_campaigns(scope_id, actor_user_id=actor_user_id, db=db)
    finally:
        deals.get_scope_or_404 = original


__all__ = ["generate_campaigns", "get_scope_or_404", "router"]
