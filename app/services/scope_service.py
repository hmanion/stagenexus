"""Compatibility shim for Scope service.

The implementation currently lives in `deal_service.py` while imports are
being migrated.
"""

from app.services.deal_service import ScopeService

__all__ = ["ScopeService"]

