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
from app.services.ops_defaults_service import APP_CONTROL_IDS, OpsDefaultsService


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

    def role_permissions_payload(self) -> dict:
        defaults = OpsDefaultsService(self.db).get()
        role_permissions = defaults.get("role_permissions") or {}
        return {
            "role_flags": role_permissions.get("role_flags") or {},
            "control_permissions": role_permissions.get("control_permissions") or {},
        }

    def identity_permissions_payload(self) -> dict:
        defaults = OpsDefaultsService(self.db).get()
        identity_permissions = defaults.get("identity_permissions") or {}
        legacy_controls = identity_permissions.get("control_permissions") or {}
        campaign_controls = identity_permissions.get("campaign_control_permissions") or {}
        app_controls = identity_permissions.get("app_control_permissions") or {}
        return {
            "screen_flags": identity_permissions.get("screen_flags") or {},
            "control_permissions": legacy_controls,
            "campaign_control_permissions": campaign_controls,
            "app_control_permissions": app_controls,
        }

    @staticmethod
    def identity_rule_allows(
        rule: dict | None,
        *,
        team: TeamName,
        seniority: SeniorityLevel,
        app_role: AppAccessRole,
    ) -> bool:
        if app_role == AppAccessRole.SUPERADMIN:
            return True
        if not isinstance(rule, dict):
            return False
        teams = {str(v) for v in (rule.get("teams") or [])}
        seniorities = {str(v) for v in (rule.get("seniorities") or [])}
        app_roles = {str(v) for v in (rule.get("app_roles") or [])}
        return (team.value in teams) and (seniority.value in seniorities) and (app_role.value in app_roles)

    @staticmethod
    def identity_campaign_rule_allows(
        rule: dict | None,
        *,
        team: TeamName,
        seniority: SeniorityLevel,
        app_role: AppAccessRole,
    ) -> bool:
        if app_role == AppAccessRole.SUPERADMIN:
            return True
        if not isinstance(rule, dict):
            return False
        teams = {str(v) for v in (rule.get("teams") or [])}
        seniorities = {str(v) for v in (rule.get("seniorities") or [])}
        return (team.value in teams) and (seniority.value in seniorities)

    @staticmethod
    def identity_app_rule_allows(
        rule: dict | None,
        *,
        seniority: SeniorityLevel,
        app_role: AppAccessRole,
    ) -> bool:
        if app_role == AppAccessRole.SUPERADMIN:
            return True
        if not isinstance(rule, dict):
            return False
        seniorities = {str(v) for v in (rule.get("seniorities") or [])}
        app_roles = {str(v) for v in (rule.get("app_roles") or [])}
        return (seniority.value in seniorities) and (app_role.value in app_roles)

    @staticmethod
    def is_app_control(control_id: str) -> bool:
        return str(control_id).startswith("admin_") or control_id in APP_CONTROL_IDS

    def has_control_permission(
        self,
        actor: Actor,
        control_id: str,
        fallback_allowed_roles: set[RoleName] | None = None,
    ) -> bool:
        if actor.app_role == AppAccessRole.SUPERADMIN:
            return True

        identity_payload = self.identity_permissions_payload()
        if self.is_app_control(control_id):
            app_rule = (identity_payload.get("app_control_permissions") or {}).get(control_id)
            if self.identity_app_rule_allows(
                app_rule,
                seniority=actor.seniority,
                app_role=actor.app_role,
            ):
                return True
        else:
            campaign_rule = (identity_payload.get("campaign_control_permissions") or {}).get(control_id)
            if self.identity_campaign_rule_allows(
                campaign_rule,
                team=actor.primary_team,
                seniority=actor.seniority,
                app_role=actor.app_role,
            ):
                return True

        identity_rule = (identity_payload.get("control_permissions") or {}).get(control_id)
        if self.identity_rule_allows(
            identity_rule,
            team=actor.primary_team,
            seniority=actor.seniority,
            app_role=actor.app_role,
        ):
            return True

        configured = (self.role_permissions_payload().get("control_permissions") or {}).get(control_id)
        if isinstance(configured, list):
            allowed_values = {str(v) for v in configured}
            if any(role.value in allowed_values for role in actor.roles):
                return True

        if fallback_allowed_roles:
            return bool(actor.roles.intersection(fallback_allowed_roles))
        return False

    def require_control_permission(
        self,
        actor: Actor,
        control_id: str,
        fallback_allowed_roles: set[RoleName] | None = None,
        *,
        detail: str = "insufficient role permissions",
    ) -> None:
        if self.has_control_permission(actor, control_id, fallback_allowed_roles):
            return
        raise HTTPException(status_code=403, detail=detail)

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
