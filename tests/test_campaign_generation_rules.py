from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.scopes import generate_campaigns
from app.models.domain import (
    CampaignType,
    Campaign,
    Deliverable,
    DeliverableType,
    Milestone,
    ProductModule,
    Publication,
    PublicationName,
    Scope,
    ScopeProductLine,
    ScopeStatus,
    Stage,
    TemplateVersion,
    User,
    WorkflowStep,
)
from app.services.campaign_generation_service import CampaignGenerationService
from app.services.stage_integrity_service import StageIntegrityService
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


def test_demand_create_only_has_no_reach_promotion_or_reporting(db_session, controlled_holidays) -> None:
    scope = _seed_demand_scope_graph(db_session, mode="create_only")

    generated = CampaignGenerationService(db_session).generate_for_scope(scope)

    assert len(generated) == 4
    for campaign in generated:
        modules = {
            module.module_name
            for module in db_session.query(ProductModule).filter(ProductModule.campaign_id == campaign.id)
        }
        assert modules == {"create"}

        deliverable_types = {
            deliverable.deliverable_type
            for deliverable in db_session.query(Deliverable).filter(Deliverable.campaign_id == campaign.id)
        }
        assert DeliverableType.REPORT not in deliverable_types
        assert DeliverableType.ENGAGEMENT_LIST not in deliverable_types

        stages = {
            stage.name
            for stage in db_session.query(Stage).filter(Stage.campaign_id == campaign.id)
        }
        assert "promotion" not in stages
        assert "reporting" not in stages

        step_names = [
            step.name.lower()
            for step in db_session.query(WorkflowStep).filter(WorkflowStep.campaign_id == campaign.id)
        ]
        assert not any("social promotion" in name for name in step_names)


def test_demand_capture_has_no_promotion_or_reporting(db_session, controlled_holidays) -> None:
    scope = _seed_demand_scope_graph(db_session, mode="create_reach_capture")

    generated = CampaignGenerationService(db_session).generate_for_scope(scope)

    capture = next(c for c in generated if c.demand_track == "capture")
    modules = {
        module.module_name
        for module in db_session.query(ProductModule).filter(ProductModule.campaign_id == capture.id)
    }
    assert modules == {"capture"}

    stages = {
        stage.name
        for stage in db_session.query(Stage).filter(Stage.campaign_id == capture.id)
    }
    assert "promotion" not in stages
    assert "reporting" not in stages

    deliverable_types = {
        deliverable.deliverable_type
        for deliverable in db_session.query(Deliverable).filter(Deliverable.campaign_id == capture.id)
    }
    assert deliverable_types == {DeliverableType.LEAD_TOTAL}


def test_reconcile_deletes_empty_optional_stage_milestones(db_session) -> None:
    template = TemplateVersion(display_id="TPL-1", name="demand", version=1, workflow_json={"csv_stage_steps": []})
    db_session.add(template)
    db_session.flush()

    campaign = Campaign(
        display_id="CMP-1",
        scope_id="scope-1",
        template_version_id=template.id,
        campaign_type=CampaignType.DEMAND,
        tier="gold",
        title="Demand create only",
        demand_track="create",
        is_demand_sprint=True,
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(ProductModule(campaign_id=campaign.id, module_name="create", enabled=True))

    reporting = Stage(display_id="STG-1", campaign_id=campaign.id, name="reporting")
    promotion = Stage(display_id="STG-2", campaign_id=campaign.id, name="promotion")
    db_session.add_all([reporting, promotion])
    db_session.flush()
    db_session.add_all(
        [
            Milestone(display_id="MS-1", campaign_id=campaign.id, stage_id=reporting.id, name="report_available"),
            Milestone(display_id="MS-2", campaign_id=campaign.id, stage_id=promotion.id, name="benchmark_met"),
        ]
    )
    db_session.flush()

    StageIntegrityService(db_session).reconcile_campaign(campaign.id)
    db_session.flush()

    assert not db_session.query(Stage).filter(Stage.id.in_([reporting.id, promotion.id])).all()
    assert not db_session.query(Milestone).filter(Milestone.display_id.in_(["MS-1", "MS-2"])).all()


def test_repeat_generation_fails_safely_via_readiness_status_gate() -> None:
    db = Mock()
    scope = SimpleNamespace(status=ScopeStatus.CAMPAIGNS_GENERATED)
    with patch("app.api.routes.scopes.get_scope_or_404", return_value=scope):
        with pytest.raises(HTTPException) as exc:
            generate_campaigns("SCOPE-1", actor_user_id="actor-1", db=db)
    assert exc.value.status_code == 400
