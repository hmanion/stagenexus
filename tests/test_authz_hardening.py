from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.api.core_routes import admin_create_user, decide_capacity_override, manage_workflow_step, resolve_escalation
from app.api.permissions import can_actor_approve_scope
from app.api.router import router
from app.api.routes.campaigns import update_campaign_assignments
from app.models.domain import AppAccessRole, RoleName, SeniorityLevel, TeamName
from app.schemas.admin import AdminUserCreateIn
from app.schemas.campaigns import CampaignAssignmentsUpdateIn
from app.schemas.deliverables import CapacityOverrideDecisionIn
from app.schemas.risks import EscalationResolveIn
from app.schemas.workflow import StepManageIn


def _actor(
    *,
    roles: set[RoleName] | None = None,
    user_id: str = "actor-1",
    primary_team: TeamName = TeamName.CLIENT_SERVICES,
    seniority: SeniorityLevel = SeniorityLevel.STANDARD,
    app_role: AppAccessRole = AppAccessRole.USER,
) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        roles=roles or set(),
        primary_team=primary_team,
        seniority=seniority,
        app_role=app_role,
    )


class AuthzHardeningTests(unittest.TestCase):
    def test_api_router_import_smoke(self) -> None:
        self.assertGreater(len(router.routes), 0)

    @patch("app.api.core_routes.AuthzService")
    def test_non_admin_cannot_create_user(self, authz_service_cls: Mock) -> None:
        authz_service_cls.return_value.actor.return_value = _actor()
        authz_service_cls.return_value.has_control_permission.return_value = False

        payload = AdminUserCreateIn(
            full_name="Blocked User",
            email="blocked@example.com",
            primary_team="client_services",
            seniority="standard",
            app_role="user",
        )

        with self.assertRaises(HTTPException) as exc:
            admin_create_user(payload, actor_user_id="actor-1", db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.permissions.AuthzService")
    def test_unauthorized_actor_cannot_approve_scope(self, authz_service_cls: Mock) -> None:
        actor = _actor(primary_team=TeamName.SALES)
        authz_service_cls.return_value.has_control_permission.return_value = False

        self.assertFalse(can_actor_approve_scope(Mock(), actor))

    @patch("app.api.routes.campaigns.AuthzService")
    @patch("app.api.routes.campaigns._resolve_by_identifier")
    def test_unassigned_actor_cannot_update_campaign_assignments(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
    ) -> None:
        resolve_by_identifier.return_value = SimpleNamespace(id="campaign-1", display_id="CMP-1")
        authz_service_cls.return_value.actor.return_value = _actor()
        authz_service_cls.return_value.has_control_permission.return_value = False

        payload = CampaignAssignmentsUpdateIn(actor_user_id="actor-1", cm_user_id="user-2")

        with self.assertRaises(HTTPException) as exc:
            update_campaign_assignments("CMP-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.core_routes.AuthzService")
    @patch("app.api.core_routes._resolve_by_identifier")
    def test_non_owner_without_control_cannot_edit_step_completion(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
    ) -> None:
        resolve_by_identifier.return_value = SimpleNamespace(id="step-1", next_owner_user_id="owner-1")
        authz_service_cls.return_value.actor.return_value = _actor(user_id="actor-1")
        authz_service_cls.return_value.has_control_permission.return_value = False

        payload = StepManageIn(actor_user_id="actor-1", completion_date_iso="2026-05-06")

        with self.assertRaises(HTTPException) as exc:
            manage_workflow_step("STEP-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.core_routes.AuthzService")
    def test_non_ops_actor_cannot_resolve_escalation(self, authz_service_cls: Mock) -> None:
        authz_service_cls.return_value.actor.return_value = _actor()
        authz_service_cls.return_value.require_any.side_effect = HTTPException(
            status_code=403,
            detail="insufficient role permissions",
        )

        payload = EscalationResolveIn(actor_user_id="actor-1")

        with self.assertRaises(HTTPException) as exc:
            resolve_escalation("ESC-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.core_routes.AuthzService")
    @patch("app.api.core_routes._resolve_by_identifier")
    def test_non_ops_actor_cannot_decide_capacity_override(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
    ) -> None:
        resolve_by_identifier.return_value = SimpleNamespace(id="cap-1", display_id="CAP-1")
        authz_service_cls.return_value.actor.return_value = _actor()
        authz_service_cls.return_value.require_any.side_effect = HTTPException(
            status_code=403,
            detail="insufficient role permissions",
        )

        payload = CapacityOverrideDecisionIn(actor_user_id="actor-1", approve=True, reason="Denied")

        with self.assertRaises(HTTPException) as exc:
            decide_capacity_override("CAP-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
