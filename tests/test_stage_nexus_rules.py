from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from app.models.domain import DeliverableStage, DeliverableType, MilestoneSlaHealth, StatusSource, TeamName
from app.services.deliverable_derivation_service import DeliverableDerivationService
from app.services.milestone_service import MilestoneService
from app.services.status_rollup_service import StatusRollupService
from app.services.team_inference_service import TeamInferenceService


class MilestoneServiceRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.service = MilestoneService(self.db)

    def test_evaluate_sla_not_due_met_and_missed(self) -> None:
        today = date(2026, 4, 16)
        future = SimpleNamespace(due_date=today + timedelta(days=3), current_target_date=None, baseline_date=None, completion_date=None, achieved_at=None)
        met = SimpleNamespace(due_date=today, current_target_date=None, baseline_date=None, completion_date=today, achieved_at=None)
        missed = SimpleNamespace(due_date=today, current_target_date=None, baseline_date=None, completion_date=today + timedelta(days=1), achieved_at=None)

        self.assertEqual(self.service.evaluate_sla(future, today=today).sla_health, MilestoneSlaHealth.NOT_DUE)
        self.assertEqual(self.service.evaluate_sla(met, today=today).sla_health, MilestoneSlaHealth.MET)
        self.assertEqual(self.service.evaluate_sla(missed, today=today).sla_health, MilestoneSlaHealth.MISSED)

    def test_refresh_sla_respects_manual_override(self) -> None:
        milestone = SimpleNamespace(
            due_date=date(2026, 4, 10),
            current_target_date=None,
            baseline_date=None,
            completion_date=None,
            achieved_at=None,
            sla_health=MilestoneSlaHealth.MET,
            sla_health_manual_override=True,
        )

        refreshed = self.service.refresh_sla(milestone)
        self.assertIs(refreshed, milestone)
        self.assertEqual(refreshed.sla_health, MilestoneSlaHealth.MET)

    def _milestone(
        self,
        *,
        milestone_id: str,
        display_id: str,
        offset: int | str | None,
        due_date: date | None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id=milestone_id,
            display_id=display_id,
            offset_days_from_campaign_start=offset,
            due_date=due_date,
            current_target_date=due_date,
            baseline_date=due_date,
            completion_date=None,
            achieved_at=None,
            sla_health=MilestoneSlaHealth.NOT_DUE,
            sla_health_manual_override=False,
        )

    def test_reanchor_campaign_milestones_valid_offsets(self) -> None:
        campaign = SimpleNamespace(id="campaign-1", planned_start_date=date(2026, 1, 5))
        milestones = [
            self._milestone(milestone_id="m-1", display_id="MS-1", offset=1, due_date=date(2026, 1, 6)),
            self._milestone(milestone_id="m-2", display_id="MS-2", offset=3, due_date=date(2026, 1, 8)),
        ]
        self.db.scalars.return_value.all.return_value = milestones

        result = self.service.reanchor_campaign_milestones(campaign)

        self.assertEqual(result.moved, 2)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.warnings, [])
        self.assertEqual(milestones[0].due_date, date(2026, 1, 6))
        self.assertEqual(milestones[1].due_date, date(2026, 1, 8))

    def test_reanchor_campaign_milestones_invalid_offset_uses_fallback_due_date(self) -> None:
        campaign = SimpleNamespace(id="campaign-1", planned_start_date=date(2026, 1, 5))
        milestone = self._milestone(
            milestone_id="m-1",
            display_id="MS-1",
            offset="bad-offset",
            due_date=date(2026, 1, 9),
        )
        self.db.scalars.return_value.all.return_value = [milestone]

        result = self.service.reanchor_campaign_milestones(campaign)

        self.assertEqual(result.moved, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.warnings, [])
        self.assertEqual(milestone.offset_days_from_campaign_start, 4)
        self.assertEqual(milestone.due_date, date(2026, 1, 12))

    def test_reanchor_campaign_milestones_out_of_range_offset_is_skipped(self) -> None:
        campaign = SimpleNamespace(id="campaign-1", planned_start_date=date(2026, 1, 5))
        milestone = self._milestone(
            milestone_id="m-1",
            display_id="MS-1",
            offset=10**9,
            due_date=date(2026, 1, 6),
        )
        original_due = milestone.due_date
        self.db.scalars.return_value.all.return_value = [milestone]

        result = self.service.reanchor_campaign_milestones(campaign)

        self.assertEqual(result.moved, 0)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].reason, "offset_out_of_range")
        self.assertEqual(milestone.due_date, original_due)

    def test_reanchor_campaign_milestones_missing_offset_backfills_from_due(self) -> None:
        campaign = SimpleNamespace(id="campaign-1", planned_start_date=date(2026, 1, 5))
        milestone = self._milestone(
            milestone_id="m-1",
            display_id="MS-1",
            offset=None,
            due_date=date(2026, 1, 7),
        )
        self.db.scalars.return_value.all.return_value = [milestone]

        result = self.service.reanchor_campaign_milestones(campaign)

        self.assertEqual(result.moved, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.warnings, [])
        self.assertEqual(milestone.offset_days_from_campaign_start, 2)
        self.assertEqual(milestone.due_date, date(2026, 1, 7))


class DeliverableDerivationRuleTests(unittest.TestCase):
    def test_assign_sequence_and_title_resets_per_type_within_campaign(self) -> None:
        existing = [
            SimpleNamespace(id="d1", sequence_number=1, deliverable_type=DeliverableType.ARTICLE),
            SimpleNamespace(id="d2", sequence_number=2, deliverable_type=DeliverableType.ARTICLE),
        ]
        db = Mock()
        db.scalars.return_value.all.return_value = existing
        service = DeliverableDerivationService(db)

        deliverable = SimpleNamespace(
            id="d3",
            campaign_id="camp-1",
            deliverable_type=DeliverableType.ARTICLE,
            sequence_number=None,
            title="",
        )
        updated = service.assign_sequence_and_title(deliverable)

        self.assertEqual(updated.sequence_number, 3)
        self.assertEqual(updated.title, "Article 3")

    def test_derive_operational_stage_status_from_most_active_stage(self) -> None:
        in_progress_steps = [
            SimpleNamespace(stage_name="production", normalized_status="in_progress"),
            SimpleNamespace(stage_name="production", normalized_status="in_progress"),
            SimpleNamespace(stage_name="planning", normalized_status="in_progress"),
        ]
        db = Mock()
        db.scalars.return_value.all.return_value = in_progress_steps
        service = DeliverableDerivationService(db)

        deliverable = SimpleNamespace(id="d1")
        stage = service.derive_operational_stage_status(deliverable)

        self.assertEqual(stage, DeliverableStage.PRODUCTION)


class TeamInferenceRuleTests(unittest.TestCase):
    def test_canonical_team_key_editorial_subteams(self) -> None:
        self.assertEqual(TeamInferenceService.canonical_team_key(TeamName.EDITORIAL, "cx"), "editorial:cx")
        self.assertEqual(TeamInferenceService.canonical_team_key(TeamName.EDITORIAL, "uc"), "editorial:uc")
        self.assertEqual(TeamInferenceService.canonical_team_key(TeamName.MARKETING, None), "marketing")


class StatusRollupRuleTests(unittest.TestCase):
    def test_manual_campaign_status_sets_override_metadata(self) -> None:
        db = Mock()
        service = StatusRollupService(db)
        campaign = SimpleNamespace(
            status="not_started",
            status_source=StatusSource.DERIVED,
            status_overridden_by_user_id=None,
            status_overridden_at=None,
        )

        service.set_manual_campaign_status(campaign, "in_progress", "u-1")

        self.assertEqual(campaign.status, "in_progress")
        self.assertEqual(campaign.status_source, StatusSource.MANUAL)
        self.assertEqual(campaign.status_overridden_by_user_id, "u-1")
        self.assertIsNotNone(campaign.status_overridden_at)


if __name__ == "__main__":
    unittest.main()
