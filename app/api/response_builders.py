from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.domain import Client, Scope
from app.schemas.scopes import ScopeOut


def build_scope_out(db: Session, scope: Scope) -> ScopeOut:
    client = db.get(Client, scope.client_id)
    return ScopeOut(
        id=scope.display_id,
        status=scope.status.value,
        client_name=client.name if client else None,
        brand_publication=scope.brand_publication.value,
    )


def build_scope_timeframe_response(scope: Scope) -> dict[str, str | None]:
    return {
        "scope_id": scope.display_id,
        "sow_start_date": scope.sow_start_date.isoformat() if scope.sow_start_date else None,
        "sow_end_date": scope.sow_end_date.isoformat() if scope.sow_end_date else None,
    }
