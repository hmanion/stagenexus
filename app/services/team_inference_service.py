from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Campaign, CampaignAssignment, TeamName, User


class TeamInferenceService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def canonical_team_key(team: TeamName | str, editorial_subteam: str | None = None) -> str:
        team_value = str(team.value if hasattr(team, "value") else team).strip().lower()
        if team_value != "editorial":
            return team_value
        sub = str(editorial_subteam or "").strip().lower()
        if sub in {"cx", "uc"}:
            return f"editorial:{sub}"
        return "editorial"

    def infer_scope_team_key(self, deal_id: str) -> str | None:
        campaigns = self.db.scalars(select(Campaign).where(Campaign.deal_id == deal_id)).all()
        if not campaigns:
            return None
        campaign_ids = [c.id for c in campaigns]
        assignments = self.db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id.in_(campaign_ids))).all()
        user_ids = sorted({a.user_id for a in assignments if a.user_id})
        users = {u.id: u for u in self.db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        counts: Counter[str] = Counter()
        for assignment in assignments:
            user = users.get(assignment.user_id)
            if not user:
                continue
            key = self.canonical_team_key(user.primary_team, getattr(user, "editorial_subteam", None))
            counts[key] += 1
        if not counts:
            return None
        return counts.most_common(1)[0][0]
