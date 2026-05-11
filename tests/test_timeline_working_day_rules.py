from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.models.domain import Milestone, MilestoneSlaHealth
from app.services.calendar_service import build_default_working_calendar
from app.services.milestone_service import MilestoneService


def test_working_calendar_never_returns_friday_to_sunday(controlled_holidays) -> None:
    calendar = build_default_working_calendar()
    adjusted = calendar.next_working_day_on_or_after(date(2026, 1, 9))  # Friday
    assert adjusted.weekday() in {0, 1, 2, 3}


def test_holiday_skip_uses_controlled_fixture(controlled_holidays) -> None:
    calendar = build_default_working_calendar()
    # 2026-05-04 is fixture holiday and Monday; should skip to Tuesday 2026-05-05
    adjusted = calendar.next_working_day_on_or_after(date(2026, 5, 4))
    assert adjusted == date(2026, 5, 5)


def test_campaign_start_date_reanchor_moves_absolute_milestones_and_keeps_working_days(db_session, controlled_holidays) -> None:
    campaign = SimpleNamespace(id="campaign-1", planned_start_date=date(2026, 1, 9))  # Friday
    milestone = Milestone(
        display_id="MS-2026-0001",
        campaign_id="campaign-1",
        name="content_plan",
        due_date=date(2026, 1, 6),
        baseline_date=date(2026, 1, 6),
        current_target_date=date(2026, 1, 6),
        completion_date=None,
        achieved_at=None,
        offset_days_from_campaign_start=1,
        sla_health=MilestoneSlaHealth.NOT_DUE,
        sla_health_manual_override=False,
    )
    db_session.add(milestone)
    db_session.flush()

    result = MilestoneService(db_session).reanchor_campaign_milestones(campaign)

    db_session.refresh(milestone)
    assert result.moved == 1
    assert milestone.due_date.weekday() in {0, 1, 2, 3}


def test_milestone_reanchor_skips_when_offset_out_of_range(db_session) -> None:
    campaign = SimpleNamespace(id="campaign-1", planned_start_date=date(2026, 1, 5))
    milestone = Milestone(
        display_id="MS-2026-0002",
        campaign_id="campaign-1",
        name="interview",
        due_date=date(2026, 1, 6),
        baseline_date=date(2026, 1, 6),
        current_target_date=date(2026, 1, 6),
        completion_date=None,
        achieved_at=None,
        offset_days_from_campaign_start=10**9,
        sla_health=MilestoneSlaHealth.NOT_DUE,
        sla_health_manual_override=False,
    )
    db_session.add(milestone)
    db_session.flush()

    result = MilestoneService(db_session).reanchor_campaign_milestones(campaign)

    assert result.skipped == 1
    assert result.warnings
