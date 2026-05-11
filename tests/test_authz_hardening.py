from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.api.core_routes import (
    admin_create_user,
    decide_capacity_override,
    decide_sow_change_request,
    manage_workflow_step,
    resolve_escalation,
    run_ops_risk_capacity_job,
)
from app.api.permissions import can_actor_approve_scope
from app.api.router import router
from app.api.routes.scopes import generate_campaigns, update_scope_content
from app.api.routes.campaigns import update_campaign_assignments
from app.models.domain import AppAccessRole, ScopeStatus, RoleName, SeniorityLevel, TeamName
from app.schemas.admin import AdminUserCreateIn
from app.schemas.campaigns import CampaignAssignmentsUpdateIn
from app.schemas.scopes import ScopeContentUpdateIn, SowChangeApproveIn
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
        authz_service_cls.return_value.resolve_actor_identity.return_value = (_actor(), "actor-1")
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
        authz_service_cls.return_value.resolve_actor_identity.return_value = (_actor(), "actor-1")
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
        authz_service_cls.return_value.resolve_actor_identity.return_value = (_actor(user_id="actor-1"), "actor-1")
        authz_service_cls.return_value.has_control_permission.return_value = False

        payload = StepManageIn(actor_user_id="actor-1", completion_date_iso="2026-05-06")

        with self.assertRaises(HTTPException) as exc:
            manage_workflow_step("STEP-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.core_routes.AuthzService")
    def test_non_ops_actor_cannot_resolve_escalation(self, authz_service_cls: Mock) -> None:
        authz_service_cls.return_value.resolve_actor_identity.return_value = (_actor(), "actor-1")
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
        authz_service_cls.return_value.resolve_actor_identity.return_value = (_actor(), "actor-1")
        authz_service_cls.return_value.require_any.side_effect = HTTPException(
            status_code=403,
            detail="insufficient role permissions",
        )

        payload = CapacityOverrideDecisionIn(actor_user_id="actor-1", approve=True, reason="Denied")

        with self.assertRaises(HTTPException) as exc:
            decide_capacity_override("CAP-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.routes.scopes.AuthzService")
    @patch("app.api.routes.scopes.get_scope_or_404")
    def test_non_owner_cannot_update_protected_scope_fields(self, get_scope_or_404: Mock, authz_service_cls: Mock) -> None:
        get_scope_or_404.return_value = SimpleNamespace(
            id="scope-1",
            display_id="SCOPE-1",
            am_user_id="owner-1",
            client_id="client-1",
            icp=None,
            campaign_objective=None,
            messaging_positioning=None,
        )
        authz_service = authz_service_cls.return_value
        authz_service.resolve_actor_identity.return_value = (_actor(user_id="user-2"), "user-2")
        authz_service.can_update_scope.return_value = False
        payload = ScopeContentUpdateIn(actor_user_id="user-2", icp="x")
        with self.assertRaises(HTTPException) as exc:
            update_scope_content("SCOPE-1", payload, db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.routes.scopes.AuthzService")
    @patch("app.api.routes.scopes.get_scope_or_404")
    @patch("app.api.routes.scopes.get_actor")
    def test_campaign_generation_blocked_for_unauthorized_actor(
        self, get_actor: Mock, get_scope_or_404: Mock, authz_service_cls: Mock
    ) -> None:
        get_scope_or_404.return_value = SimpleNamespace(status=ScopeStatus.READINESS_PASSED)
        get_actor.return_value = _actor(primary_team=TeamName.SALES, seniority=SeniorityLevel.STANDARD)
        with patch("app.api.routes.scopes.can_actor_generate_campaigns", return_value=False):
            with self.assertRaises(HTTPException) as exc:
                generate_campaigns("SCOPE-1", actor_user_id="user-2", db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.core_routes.AuthzService")
    def test_cc_actor_cannot_decide_sow_change(self, authz_service_cls: Mock) -> None:
        actor = _actor(roles={RoleName.CC})
        authz_service_cls.return_value.resolve_actor_identity.return_value = (actor, "user-1")
        authz_service_cls.return_value.require_any.side_effect = HTTPException(status_code=403, detail="insufficient")
        payload = SowChangeApproveIn(
            approver_user_id="user-1",
            approver_role=RoleName.HEAD_OPS.value,
            decision="approved",
        )
        with self.assertRaises(HTTPException) as exc:
            decide_sow_change_request("SCR-1", payload, actor_user_id="user-1", db=Mock())
        self.assertEqual(exc.exception.status_code, 403)

    @patch("app.api.core_routes.AuthzService")
    @patch("app.api.core_routes.OpsJobService")
    def test_am_cannot_run_ops_job(self, ops_job_service_cls: Mock, authz_service_cls: Mock) -> None:
        authz_service = authz_service_cls.return_value
        authz_service.actor.return_value = _actor(roles={RoleName.AM})
        authz_service.can_run_ops_job.return_value = False
        with self.assertRaises(HTTPException) as exc:
            run_ops_risk_capacity_job(actor_user_id="am-1", db=Mock())
        self.assertEqual(exc.exception.status_code, 403)
        ops_job_service_cls.assert_not_called()

    def test_superadmin_can_override_mismatched_claim(self) -> None:
        from app.services.authz_service import AuthzService

        authz = AuthzService(Mock())
        superadmin_actor = _actor(
            user_id="admin-1",
            roles={RoleName.ADMIN},
            app_role=AppAccessRole.SUPERADMIN,
        )
        with patch.object(authz, "actor", return_value=superadmin_actor):
            actor, effective_user_id = authz.resolve_actor_identity(
                actor_user_id="admin-1",
                claimed_user_id="delegated-user",
                claim_field="requested_by_user_id",
            )
        self.assertEqual(actor.user_id, "admin-1")
        self.assertEqual(effective_user_id, "delegated-user")


if __name__ == "__main__":
    unittest.main()
