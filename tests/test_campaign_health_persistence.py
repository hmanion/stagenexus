from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select

from app.api.core_routes import recalculate_campaign_health
from app.api.routes.campaigns import campaign_workspace, list_campaigns
from app.models.domain import (
    Campaign,
    CampaignAssignment,
    CampaignType,
    Client,
    Scope,
    Deliverable,
    DeliverableType,
    GlobalHealth,
    GlobalStatus,
    Publication,
    PublicationName,
    RoleName,
    Stage,
    TemplateVersion,
    User,
    WorkflowStep,
    Milestone,
)
from app.services.campaign_health_updater import refresh_campaign_health
from app.services.deliverable_workflow_service import DeliverableWorkflowService
from app.services.workflow_engine_service import WorkflowEngineService


def _seed_campaign_graph(db_session, *, campaign_id: str = "campaign-1", display_id: str = "CAMP-001") -> Campaign:
    suffix = campaign_id.replace("campaign-", "").replace("-", "")
    user = User(id=f"user-{suffix}", email=f"u{suffix}@example.com", full_name=f"User {suffix}")
    client = Client(id=f"client-{suffix}", name=f"Client {suffix}")
    publication = db_session.scalar(select(Publication).where(Publication.name == PublicationName.UC_TODAY))
    if not publication:
        publication = Publication(id="pub-1", name=PublicationName.UC_TODAY)
    template = TemplateVersion(
        id=f"tpl-{suffix}",
        display_id=f"TPL-{suffix}",
        name=f"Default-{suffix}",
        version=max(len(suffix), 1),
        workflow_json={},
    )
    scope = Scope(
        id=f"scope-{suffix}",
        display_id=f"SCOPE-{suffix}",
        client_id=client.id,
        am_user_id=user.id,
        brand_publication=PublicationName.UC_TODAY,
        sow_start_date=date(2026, 1, 1),
        sow_end_date=date(2026, 12, 31),
    )
    campaign = Campaign(
        id=campaign_id,
        display_id=display_id,
        scope_id=scope.id,
        template_version_id=template.id,
        campaign_type=CampaignType.DEMAND,
        tier="gold",
        title=f"Campaign {display_id}",
        status="not_started",
        health=GlobalHealth.AT_RISK,
        health_reason="seeded",
        planned_start_date=date(2026, 1, 5),
        planned_end_date=date(2026, 3, 5),
    )
    assignment = CampaignAssignment(
        id=f"assign-{campaign_id}",
        campaign_id=campaign.id,
        role_name=RoleName.CM,
        user_id=user.id,
    )

    db_session.add_all([user, client, template, scope, campaign, assignment])
    if publication is not None and db_session.get(Publication, publication.id) is None:
        db_session.add(publication)
    db_session.commit()
    return campaign


def test_campaign_list_uses_live_timeline_health_for_pill(db_session):
    campaign = _seed_campaign_graph(db_session)

    with patch("app.api.routes.campaigns.TimelineHealthService.evaluate_campaign") as mocked_eval:
        mocked_eval.return_value = (
            SimpleNamespace(health="off_track", health_reason="stage_off_track_rollup"),
            "production",
        )
        payload = list_campaigns(limit=25, offset=0, db=db_session)

    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["id"] == campaign.display_id
    assert item["health"] == "off_track"
    assert item["campaign_health"] == "off_track"
    assert item["health_reason"] == "stage_off_track_rollup"
    assert "deliverables" not in item
    assert "work_steps" not in item
    mocked_eval.assert_called_once()


def test_campaign_list_paginates_before_assembly(db_session):
    _seed_campaign_graph(db_session, campaign_id="campaign-a", display_id="CAMP-A")
    _seed_campaign_graph(db_session, campaign_id="campaign-b", display_id="CAMP-B")
    _seed_campaign_graph(db_session, campaign_id="campaign-c", display_id="CAMP-C")

    payload = list_campaigns(limit=1, offset=1, db=db_session)
    assert payload["total"] == 3
    assert len(payload["items"]) == 1


def test_campaign_workspace_still_returns_child_details(db_session):
    campaign = _seed_campaign_graph(db_session, campaign_id="campaign-ws", display_id="CAMP-WS")
    stage = Stage(
        id="stage-ws",
        display_id="STG-WS",
        campaign_id=campaign.id,
        name="production",
        status=GlobalStatus.IN_PROGRESS,
        health=GlobalHealth.AT_RISK,
    )
    deliverable = Deliverable(
        id="deliverable-ws",
        display_id="DEL-WS",
        campaign_id=campaign.id,
        publication_id="pub-1",
        deliverable_type=DeliverableType.ARTICLE,
        title="Workspace Deliverable",
        current_start=date(2026, 1, 5),
        current_due=date(2026, 1, 20),
    )
    step = WorkflowStep(
        id="step-ws",
        display_id="STEP-WS",
        campaign_id=campaign.id,
        stage_id=stage.id,
        linked_deliverable_id=deliverable.id,
        name="Workspace Step",
        owner_role=RoleName.CM,
        current_start=date(2026, 1, 10),
        current_due=date(2026, 1, 12),
    )
    milestone = Milestone(
        id="milestone-ws",
        display_id="MIL-WS",
        campaign_id=campaign.id,
        name="Workspace Milestone",
        baseline_date=date(2026, 1, 15),
        current_target_date=date(2026, 1, 16),
    )
    db_session.add_all([stage, deliverable, step, milestone])
    db_session.commit()

    payload = campaign_workspace(campaign.display_id, db=db_session)

    assert payload["campaign"]["id"] == campaign.display_id
    assert len(payload["deliverables"]["items"]) >= 1
    assert payload["deliverables"]["items"][0]["current_step_name"] == "Workspace Step"
    assert len(payload["workflow_steps"]["items"]) >= 1
    assert len(payload["timeline"]["milestones"]) >= 1


def test_step_completion_refreshes_parent_campaign_health(db_session):
    campaign = _seed_campaign_graph(db_session)
    stage = Stage(
        id="stage-1",
        display_id="STG-001",
        campaign_id=campaign.id,
        name="production",
        status=GlobalStatus.IN_PROGRESS,
        health=GlobalHealth.AT_RISK,
    )
    step = WorkflowStep(
        id="step-1",
        display_id="STEP-001",
        campaign_id=campaign.id,
        stage_id=stage.id,
        name="Write draft",
        owner_role=RoleName.CM,
        current_start=date(2026, 1, 10),
        current_due=date(2026, 1, 12),
    )
    db_session.add_all([stage, step])
    db_session.commit()

    WorkflowEngineService(db_session).set_step_complete(step.id, actor_user_id="user-1", enforce_next_owner=False)
    db_session.commit()
    db_session.refresh(campaign)

    assert campaign.health_updated_at is not None


def test_override_due_refreshes_parent_campaign_health(db_session):
    campaign = _seed_campaign_graph(db_session)
    stage = Stage(
        id="stage-2",
        display_id="STG-002",
        campaign_id=campaign.id,
        name="production",
        status=GlobalStatus.IN_PROGRESS,
        health=GlobalHealth.AT_RISK,
    )
    step = WorkflowStep(
        id="step-2",
        display_id="STEP-002",
        campaign_id=campaign.id,
        stage_id=stage.id,
        name="Client review",
        owner_role=RoleName.CM,
        current_start=date(2026, 1, 10),
        current_due=date(2026, 1, 12),
    )
    db_session.add_all([stage, step])
    db_session.commit()

    WorkflowEngineService(db_session).override_step_due(step.id, "2026-01-20")
    db_session.commit()
    db_session.refresh(campaign)

    assert campaign.health_updated_at is not None


def test_deliverable_transition_refreshes_parent_campaign_health(db_session):
    campaign = _seed_campaign_graph(db_session)
    deliverable = Deliverable(
        id="deliverable-1",
        display_id="DEL-001",
        campaign_id=campaign.id,
        publication_id="pub-1",
        deliverable_type=DeliverableType.ARTICLE,
        title="Article",
        current_start=date(2026, 1, 5),
        current_due=date(2026, 1, 20),
    )
    db_session.add(deliverable)
    db_session.commit()

    DeliverableWorkflowService(db_session).transition(
        deliverable=deliverable,
        to_status="in_progress",
        actor_user_id="user-1",
        actor_roles={RoleName.CM},
    )
    db_session.commit()
    db_session.refresh(campaign)

    assert campaign.health_updated_at is not None


def test_stage_off_track_guardrail_persisted_on_campaign(db_session):
    campaign = _seed_campaign_graph(db_session)
    campaign.health = GlobalHealth.ON_TRACK
    campaign.health_reason = "forced_seed"
    stage = Stage(
        id="stage-guardrail",
        display_id="STG-GR",
        campaign_id=campaign.id,
        name="production",
        status=GlobalStatus.IN_PROGRESS,
        health=GlobalHealth.OFF_TRACK,
    )
    db_session.add(stage)
    db_session.commit()

    refresh_campaign_health(db_session, campaign.id)
    db_session.commit()
    db_session.refresh(campaign)

    assert campaign.health == GlobalHealth.OFF_TRACK
    assert campaign.health != GlobalHealth.ON_TRACK


def test_reconciliation_endpoint_repairs_stale_health(db_session):
    campaign = _seed_campaign_graph(db_session)
    campaign.health = GlobalHealth.ON_TRACK
    campaign.health_reason = "stale"
    stage = Stage(
        id="stage-reconcile",
        display_id="STG-REC",
        campaign_id=campaign.id,
        name="production",
        status=GlobalStatus.IN_PROGRESS,
        health=GlobalHealth.OFF_TRACK,
    )
    db_session.add(stage)
    db_session.commit()

    with patch("app.api.core_routes.AuthzService") as authz_cls:
        authz = authz_cls.return_value
        authz.actor.return_value = object()
        authz.can_run_ops_job.return_value = True
        payload = recalculate_campaign_health(actor_user_id="user-1", db=db_session)

    db_session.refresh(campaign)
    assert payload["processed"] >= 1
    assert payload["updated"] >= 1
    assert campaign.health == GlobalHealth.OFF_TRACK
    assert campaign.health != GlobalHealth.ON_TRACK
    assert campaign.health_updated_at is not None
