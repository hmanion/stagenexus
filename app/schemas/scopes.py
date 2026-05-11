"""Compatibility shim for Scope schemas.

Scope payload models currently live in `app.schemas.deals` during the
Deal -> Scope migration window. Importing from this module keeps legacy
imports stable.
"""

from app.schemas.deals import (
    OpsApproveIn,
    ScopeAmUpdateIn,
    ScopeContentUpdateIn,
    ScopeCreateIn,
    ScopeDeleteIn,
    ScopeOut,
    ScopeTimeframeUpdateIn,
    SowChangeApproveIn,
    SowChangeCreateIn,
)

__all__ = [
    "OpsApproveIn",
    "ScopeAmUpdateIn",
    "ScopeContentUpdateIn",
    "ScopeCreateIn",
    "ScopeDeleteIn",
    "ScopeOut",
    "ScopeTimeframeUpdateIn",
    "SowChangeApproveIn",
    "SowChangeCreateIn",
]

