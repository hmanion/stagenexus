from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.domain import Campaign, Client, Scope
from app.services.campaign_generation_service import CampaignGenerationService


def main() -> None:
    updated = 0
    inspected = 0
    with SessionLocal() as db:
        naming = CampaignGenerationService(db)
        campaigns = db.scalars(select(Campaign)).all()
        scopes = {d.id: d for d in db.scalars(select(Scope)).all()}
        clients = {c.id: c for c in db.scalars(select(Client)).all()}
        for campaign in campaigns:
            inspected += 1
            scope = scopes.get(campaign.scope_id)
            if not scope:
                continue
            client = clients.get(scope.client_id)
            desired = naming._campaign_title(  # noqa: SLF001
                client_name=((client.name.split()[0] if (client and client.name) else "Client")),
                scope=scope,
                campaign_type=campaign.campaign_type,
                tier=campaign.tier,
                demand_track=campaign.demand_track,
                demand_sprint_number=campaign.demand_sprint_number,
            )
            if (campaign.title or "").strip() == desired:
                continue
            campaign.title = desired
            updated += 1
        db.commit()
    print(f"Inspected: {inspected}")
    print(f"Updated titles: {updated}")


if __name__ == "__main__":
    main()
