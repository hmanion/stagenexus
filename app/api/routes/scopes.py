"""Compatibility shim for Scope routes.

Scope endpoints are currently defined in `deals.py` during migration.
"""

from app.api.routes.deals import router

__all__ = ["router"]

