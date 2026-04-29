from __future__ import annotations

from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.api.routes.campaigns import update_campaign_dates
from app.schemas.campaigns import CampaignDatesUpdateIn
from app.services.milestone_service import MilestoneReanchorResult, MilestoneReanchorWarning


class CampaignDateUpdateRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.campaign = SimpleNamespace(
            id="campaign-uuid-1",
            display_id="NICE-26-RS1M-01",
            planned_start_date=date(2026, 5, 5),
            planned_end_date=date(2026, 7, 29),
        )
        self.payload = CampaignDatesUpdateIn(
            actor_user_id="actor-1",
            planned_start_iso="2026-05-06",
            planned_end_iso="2026-07-30",
        )

    @patch("app.api.routes.campaigns.PublicIdService")
    @patch("app.api.routes.campaigns.MilestoneService")
    @patch("app.api.routes.campaigns.AuthzService")
    @patch("app.api.routes.campaigns._resolve_by_identifier")
    def test_update_campaign_dates_success_response_shape(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
        milestone_service_cls: Mock,
        public_id_service_cls: Mock,
    ) -> None:
        resolve_by_identifier.return_value = self.campaign
        authz_service_cls.return_value.actor.return_value = SimpleNamespace()
        authz_service_cls.return_value.has_control_permission.return_value = True
        milestone_service_cls.return_value.reanchor_campaign_milestones.return_value = MilestoneReanchorResult(
            moved=2,
            skipped=0,
            warnings=[],
        )
        public_id_service_cls.return_value.next_id.return_value = "ACT-2026-9999"

        response = update_campaign_dates("NICE-26-RS1M-01", self.payload, self.db)

        self.assertEqual(response["campaign_id"], "NICE-26-RS1M-01")
        self.assertEqual(response["planned_start_date"], "2026-05-06")
        self.assertEqual(response["planned_end_date"], "2026-07-30")
        self.assertEqual(response["milestones_reanchored"], 2)
        self.assertEqual(response["milestones_skipped"], 0)
        self.assertEqual(response["milestone_warnings"], [])
        self.db.commit.assert_called_once()

    @patch("app.api.routes.campaigns.PublicIdService")
    @patch("app.api.routes.campaigns.MilestoneService")
    @patch("app.api.routes.campaigns.AuthzService")
    @patch("app.api.routes.campaigns._resolve_by_identifier")
    def test_update_campaign_dates_with_skips_still_succeeds_and_logs_metadata(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
        milestone_service_cls: Mock,
        public_id_service_cls: Mock,
    ) -> None:
        resolve_by_identifier.return_value = self.campaign
        authz_service_cls.return_value.actor.return_value = SimpleNamespace()
        authz_service_cls.return_value.has_control_permission.return_value = True
        milestone_service_cls.return_value.reanchor_campaign_milestones.return_value = MilestoneReanchorResult(
            moved=1,
            skipped=1,
            warnings=[
                MilestoneReanchorWarning(
                    milestone_id="m-1",
                    milestone_display_id="MS-2026-0001",
                    reason="offset_missing_or_invalid_and_no_fallback_anchor",
                )
            ],
        )
        public_id_service_cls.return_value.next_id.return_value = "ACT-2026-9999"

        response = update_campaign_dates("NICE-26-RS1M-01", self.payload, self.db)

        self.assertEqual(response["milestones_reanchored"], 1)
        self.assertEqual(response["milestones_skipped"], 1)
        self.assertEqual(len(response["milestone_warnings"]), 1)
        self.assertEqual(response["milestone_warnings"][0]["reason"], "offset_missing_or_invalid_and_no_fallback_anchor")
        added_activity_log = self.db.add.call_args[0][0]
        self.assertEqual(added_activity_log.meta_json["milestones_reanchored"], 1)
        self.assertEqual(added_activity_log.meta_json["milestones_skipped"], 1)
        self.assertEqual(len(added_activity_log.meta_json["milestone_warnings"]), 1)
        self.db.commit.assert_called_once()

    @patch("app.api.routes.campaigns.AuthzService")
    @patch("app.api.routes.campaigns._resolve_by_identifier")
    def test_update_campaign_dates_requires_at_least_one_date(
        self,
        resolve_by_identifier: Mock,
        authz_service_cls: Mock,
    ) -> None:
        resolve_by_identifier.return_value = self.campaign
        authz_service_cls.return_value.actor.return_value = SimpleNamespace()
        authz_service_cls.return_value.has_control_permission.return_value = True
        payload = CampaignDatesUpdateIn(actor_user_id="actor-1", planned_start_iso=None, planned_end_iso=None)

        with self.assertRaises(HTTPException) as exc:
            update_campaign_dates("NICE-26-RS1M-01", payload, self.db)
        self.assertEqual(exc.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
