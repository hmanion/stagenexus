from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.domain import Client, Deal
from app.schemas.deals import DealOut


def build_deal_out(db: Session, deal: Deal) -> DealOut:
    client = db.get(Client, deal.client_id)
    return DealOut(
        id=deal.display_id,
        status=deal.status.value,
        client_name=client.name if client else None,
        brand_publication=deal.brand_publication.value,
    )


def build_scope_timeframe_response(deal: Deal) -> dict[str, str | None]:
    return {
        "scope_id": deal.display_id,
        "sow_start_date": deal.sow_start_date.isoformat() if deal.sow_start_date else None,
        "sow_end_date": deal.sow_end_date.isoformat() if deal.sow_end_date else None,
    }
