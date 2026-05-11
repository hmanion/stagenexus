from __future__ import annotations

from types import SimpleNamespace

from app.models.domain import GlobalHealth, GlobalStatus, StatusSource
from app.services.status_rollup_service import StatusRollupService


def test_global_status_values_remain_valid() -> None:
    assert {s.value for s in GlobalStatus} == {
        "not_started",
        "in_progress",
        "on_hold",
        "blocked_client",
        "blocked_internal",
        "blocked_dependency",
        "done",
        "cancelled",
    }


def test_global_health_values_remain_valid() -> None:
    assert {h.value for h in GlobalHealth} == {"not_started", "on_track", "at_risk", "off_track"}


def test_campaign_status_falls_back_to_not_started_when_no_progress(db_session) -> None:
    campaign = SimpleNamespace(
        id="campaign-1",
        status="in_progress",
        status_source=StatusSource.MANUAL,
        status_overridden_by_user_id="u-1",
        status_overridden_at="x",
    )
    db_session.scalars = lambda *_args, **_kwargs: SimpleNamespace(all=lambda: [])

    StatusRollupService(db_session).reset_campaign_to_derived(campaign)

    assert campaign.status == "not_started"
    assert campaign.status_source == StatusSource.DERIVED


def test_campaign_cannot_be_on_track_when_any_stage_is_off_track(db_session) -> None:
    campaign = SimpleNamespace(
        id="campaign-1",
        status="on_track",
        status_source=StatusSource.DERIVED,
        status_overridden_by_user_id=None,
        status_overridden_at=None,
    )
    off_track_stage = SimpleNamespace(status="blocked_dependency")
    db_session.scalars = lambda *_args, **_kwargs: SimpleNamespace(all=lambda: [off_track_stage])

    StatusRollupService(db_session).reset_campaign_to_derived(campaign)

    assert campaign.status != "on_track"
    assert campaign.status == "blocked_dependency"


def test_parent_status_resets_to_derived_after_child_changes(db_session) -> None:
    stage = SimpleNamespace(
        id="stage-1",
        campaign_id="campaign-1",
        status_source=StatusSource.MANUAL,
        status_overridden_by_user_id="u-1",
        status_overridden_at="x",
    )
    campaign = SimpleNamespace(
        id="campaign-1",
        status="in_progress",
        status_source=StatusSource.MANUAL,
        status_overridden_by_user_id="u-1",
        status_overridden_at="x",
    )
    step = SimpleNamespace(stage_id="stage-1")

    def _get(model, identifier):
        if identifier == "stage-1":
            return stage
        if identifier == "campaign-1":
            return campaign
        return None

    db_session.get = _get
    db_session.scalars = lambda *_args, **_kwargs: SimpleNamespace(all=lambda: [SimpleNamespace(status="in_progress")])

    StatusRollupService(db_session).reset_parents_after_step_change(step)

    assert stage.status_source == StatusSource.DERIVED
    assert campaign.status_source == StatusSource.DERIVED
