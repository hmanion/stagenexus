from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.scopes import generate_campaigns
from app.models.domain import CampaignType, Scope, ScopeProductLine, ScopeStatus, Publication, PublicationName, TemplateVersion, User
from app.services.campaign_generation_service import CampaignGenerationService
from app.services.scope_service import ScopeService
from app.schemas.scopes import OpsApproveIn


def test_campaign_generation_blocked_before_readiness_passes() -> None:
    db = Mock()
    scope = SimpleNamespace(status=ScopeStatus.READINESS_FAILED)
    with patch("app.api.routes.scopes.get_scope_or_404", return_value=scope):
        with pytest.raises(HTTPException) as exc:
            generate_campaigns("SCOPE-1", actor_user_id="actor-1", db=db)
    assert exc.value.status_code == 400
    assert "readiness gate" in str(exc.value.detail)


def test_ops_approval_assigns_required_roles(db_session) -> None:
    scope = Scope(
        display_id="SCOPE-001",
        client_id="client-1",
        am_user_id="am-1",
        brand_publication=PublicationName.UC_TODAY,
        status=ScopeStatus.SUBMITTED,
        sow_start_date=date(2026, 1, 5),
        sow_end_date=date(2026, 4, 5),
        icp="IT leaders",
        campaign_objective="Demand",
        messaging_positioning="Clear",
    )
    db_session.add(scope)
    db_session.flush()

    payload = OpsApproveIn(
        head_ops_user_id="head-ops-1",
        cm_user_id="cm-1",
        cc_user_id="cc-1",
        ccs_user_id="ccs-1",
    )

    ScopeService(db_session).ops_approve(scope, payload)

    assert scope.assigned_cm_user_id == "cm-1"
    assert scope.assigned_cc_user_id == "cc-1"
    assert scope.assigned_ccs_user_id == "ccs-1"


def _seed_demand_scope_graph(db_session, mode: str = "create_reach_capture") -> Scope:
    db_session.add(User(id="am-1", email="am@example.com", full_name="AM User"))
    db_session.add(Publication(name=PublicationName.UC_TODAY))
    scope = Scope(
        display_id="SCOPE-DEM-001",
        client_id="client-1",
        am_user_id="am-1",
        brand_publication=PublicationName.UC_TODAY,
        status=ScopeStatus.READINESS_PASSED,
        sow_start_date=date(2026, 1, 5),
        sow_end_date=date(2026, 12, 31),
        icp="IT leaders",
        campaign_objective="Demand",
        messaging_positioning="Clear",
        readiness_passed=True,
        assigned_cm_user_id="cm-1",
        assigned_cc_user_id="cc-1",
        assigned_ccs_user_id="ccs-1",
    )
    db_session.add(scope)
    db_session.flush()
    db_session.add(
        ScopeProductLine(
            scope_id=scope.id,
            product_type=CampaignType.DEMAND,
            tier="gold",
            options_json={"demand_module_mode": mode},
        )
    )
    db_session.flush()
    return scope


def test_generated_campaigns_pin_template_version_and_create_four_sprints(db_session, controlled_holidays) -> None:
    scope = _seed_demand_scope_graph(db_session, mode="create_reach")

    generated = CampaignGenerationService(db_session).generate_for_scope(scope)

    sprint_campaigns = [c for c in generated if c.is_demand_sprint]
    assert len(sprint_campaigns) == 4

    starts = [c.planned_start_date for c in sorted(sprint_campaigns, key=lambda c: c.demand_sprint_number or 0)]
    assert starts == [date(2026, 1, 5), date(2026, 4, 5), date(2026, 7, 4), date(2026, 10, 2)]

    for campaign in sprint_campaigns:
        assert campaign.planned_end_date == campaign.planned_start_date.fromordinal(campaign.planned_start_date.toordinal() + 89)
        assert campaign.template_version_id is not None
        template = db_session.get(TemplateVersion, campaign.template_version_id)
        assert template is not None


def test_demand_capture_generates_separate_annual_campaign(db_session, controlled_holidays) -> None:
    scope = _seed_demand_scope_graph(db_session, mode="create_reach_capture")

    generated = CampaignGenerationService(db_session).generate_for_scope(scope)

    capture = [c for c in generated if c.demand_track == "capture"]
    assert len(capture) == 1
    assert capture[0].is_demand_sprint is False
    assert capture[0].planned_start_date == date(2026, 1, 5)
    assert capture[0].planned_end_date == date(2026, 12, 31)


def test_repeat_generation_fails_safely_via_readiness_status_gate() -> None:
    db = Mock()
    scope = SimpleNamespace(status=ScopeStatus.CAMPAIGNS_GENERATED)
    with patch("app.api.routes.scopes.get_scope_or_404", return_value=scope):
        with pytest.raises(HTTPException) as exc:
            generate_campaigns("SCOPE-1", actor_user_id="actor-1", db=db)
    assert exc.value.status_code == 400
