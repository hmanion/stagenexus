from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    AppAccessRole,
    Campaign,
    CampaignAssignment,
    Deal,
    SeniorityLevel,
    TeamName,
    Role,
    RoleName,
    User,
    UserRoleAssignment,
)


@dataclass
class Actor:
    user_id: str
    roles: set[RoleName]
    primary_team: TeamName
    seniority: SeniorityLevel
    app_role: AppAccessRole


class AuthzService:
    def __init__(self, db: Session):
        self.db = db

    def actor(self, user_id: str) -> Actor:
        user = self.db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="invalid actor")

        explicit_roles = set(
            self.db.scalars(
                select(Role.name)
                .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
                .where(UserRoleAssignment.user_id == user_id)
            ).all()
        )
        derived_roles = self._derived_legacy_roles(user)
        roles = set(explicit_roles).union(derived_roles)
        return Actor(
            user_id=user_id,
            roles=roles,
            primary_team=user.primary_team,
            seniority=user.seniority,
            app_role=user.app_role,
        )

    @staticmethod
    def _derived_legacy_roles(user: User) -> set[RoleName]:
        roles: set[RoleName] = set()
        if user.app_role in {AppAccessRole.ADMIN, AppAccessRole.SUPERADMIN}:
            roles.add(RoleName.ADMIN)
        if user.primary_team == TeamName.SALES:
            roles.add(RoleName.AM)
            if user.seniority in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
                roles.add(RoleName.HEAD_SALES)
        elif user.primary_team == TeamName.EDITORIAL:
            roles.add(RoleName.CC)
        elif user.primary_team == TeamName.MARKETING:
            roles.update({RoleName.DN, RoleName.MM})
        elif user.primary_team == TeamName.CLIENT_SERVICES:
            roles.add(RoleName.CM)
            if user.seniority in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
                roles.add(RoleName.HEAD_OPS)
        return roles

    def require_any(self, actor: Actor, allowed: set[RoleName]) -> None:
        if actor.roles.intersection(allowed):
            return
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    def require_deal_owner_or_roles(self, actor: Actor, deal: Deal, allowed_roles: set[RoleName]) -> None:
        if deal.am_user_id == actor.user_id:
            return
        if actor.roles.intersection(allowed_roles):
            return
        raise HTTPException(status_code=403, detail="actor cannot modify this deal")

    def require_campaign_member_or_roles(
        self,
        actor: Actor,
        campaign: Campaign,
        member_roles: set[RoleName],
        fallback_roles: set[RoleName],
    ) -> None:
        if actor.roles.intersection(fallback_roles):
            return

        assignments = self.db.scalars(
            select(CampaignAssignment.role_name).where(
                CampaignAssignment.campaign_id == campaign.id,
                CampaignAssignment.user_id == actor.user_id,
            )
        ).all()
        if set(assignments).intersection(member_roles):
            return

        raise HTTPException(status_code=403, detail="actor is not assigned to this campaign")
