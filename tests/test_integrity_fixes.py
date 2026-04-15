from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.routes import create_sow_change_request
from app.db.base import Base
from app.db.schema_updates import assert_runtime_integrity
from app.db.session import assert_sqlite_foreign_keys_enabled
from app.models.domain import RoleName, SowChangeRequest
from app.schemas.deals import SowChangeCreateIn
from app.services.change_control_service import ChangeControlService


class ChangeControlServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db = SessionLocal()
        self.service = ChangeControlService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_apply_approval_accepts_display_id_and_activates(self) -> None:
        req = self.service.create_request(
            campaign_id="c" * 36,
            requested_by_user_id="u-requestor",
            impact_scope_json={"timeline": "+5 working days"},
        )
        self.db.flush()

        self.service.apply_approval(req.display_id, "u-ops", RoleName.HEAD_OPS, "approved")
        updated = self.service.apply_approval(req.display_id, "u-sales", RoleName.HEAD_SALES, "approved")

        self.assertEqual(updated.status, "activated")
        self.assertIsNotNone(updated.activated_at)

    def test_apply_approval_missing_rows_is_actionable(self) -> None:
        req = SowChangeRequest(
            display_id="SOW-MISSING-APPROVALS",
            campaign_id="c" * 36,
            requested_by_user_id="u-requestor",
            impact_scope_json={},
            status="pending",
        )
        self.db.add(req)
        self.db.flush()

        with self.assertRaises(ValueError) as exc:
            self.service.apply_approval(req.display_id, "u-ops", RoleName.HEAD_OPS, "approved")
        self.assertIn("missing seeded approval rows", str(exc.exception))


class RouteCanonicalIdTests(unittest.TestCase):
    @patch("app.api.routes.ChangeControlService")
    @patch("app.api.routes.AuthzService")
    @patch("app.api.routes._resolve_by_identifier")
    def test_create_sow_change_request_uses_campaign_uuid(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
        change_control_service_cls: Mock,
    ) -> None:
        db = Mock()
        campaign = SimpleNamespace(id="12345678-1234-1234-1234-123456789012")
        resolve_by_identifier.return_value = campaign

        authz_instance = Mock()
        authz_instance.actor.return_value = SimpleNamespace(roles={RoleName.CM})
        authz_service_cls.return_value = authz_instance

        change_control_instance = Mock()
        change_control_instance.create_request.return_value = SimpleNamespace(display_id="SOW-001", status="pending")
        change_control_service_cls.return_value = change_control_instance

        payload = SowChangeCreateIn(requested_by_user_id="u-requestor", impact_scope_json={"scope": "update"})
        response = create_sow_change_request(
            campaign_id="CMP-001",
            payload=payload,
            actor_user_id="u-requestor",
            db=db,
        )

        self.assertEqual(response["id"], "SOW-001")
        self.assertEqual(response["status"], "pending")
        change_control_instance.create_request.assert_called_once_with(
            campaign_id=campaign.id,
            requested_by_user_id="u-requestor",
            impact_scope_json={"scope": "update"},
        )


class RuntimeGuardTests(unittest.TestCase):
    def test_assert_sqlite_foreign_keys_enabled_raises_when_off(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        with self.assertRaises(RuntimeError):
            assert_sqlite_foreign_keys_enabled(engine)
        engine.dispose()

    def test_assert_sqlite_foreign_keys_enabled_passes_when_on(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert_sqlite_foreign_keys_enabled(engine)
        engine.dispose()

    def test_assert_runtime_integrity_raises_for_malformed_campaign_id(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE campaigns (id VARCHAR(36) PRIMARY KEY)"))
            conn.execute(
                text(
                    """
                    CREATE TABLE sow_change_requests (
                        id VARCHAR(36) PRIMARY KEY,
                        campaign_id VARCHAR(36),
                        requested_by_user_id VARCHAR(36),
                        impact_scope_json TEXT,
                        status VARCHAR(32)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sow_change_requests (id, campaign_id, requested_by_user_id, impact_scope_json, status)
                    VALUES ('req-1', 'bad', 'user-1', '{}', 'pending')
                    """
                )
            )

        with self.assertRaises(RuntimeError) as exc:
            assert_runtime_integrity(engine)
        self.assertIn("malformed campaign_id", str(exc.exception))
        engine.dispose()

    def test_assert_runtime_integrity_raises_for_orphan_campaign_reference(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE campaigns (id VARCHAR(36) PRIMARY KEY)"))
            conn.execute(
                text(
                    """
                    CREATE TABLE sow_change_requests (
                        id VARCHAR(36) PRIMARY KEY,
                        campaign_id VARCHAR(36),
                        requested_by_user_id VARCHAR(36),
                        impact_scope_json TEXT,
                        status VARCHAR(32)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO sow_change_requests (id, campaign_id, requested_by_user_id, impact_scope_json, status)
                    VALUES ('req-1', '12345678-1234-1234-1234-123456789012', 'user-1', '{}', 'pending')
                    """
                )
            )

        with self.assertRaises(RuntimeError) as exc:
            assert_runtime_integrity(engine)
        self.assertIn("reference missing campaigns", str(exc.exception))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
