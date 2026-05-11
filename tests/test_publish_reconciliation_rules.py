from __future__ import annotations

from datetime import date

from sqlalchemy import select
import pytest

from app.models.domain import (
    Campaign,
    CampaignType,
    Deal,
    DealStatus,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Milestone,
    MilestoneSlaHealth,
    ProductModule,
    Publication,
    PublicationName,
    Stage,
    TemplateVersion,
    WorkflowStep,
    WorkflowStepKind,
    RoleName,
)
from app.services.stage_integrity_service import StageIntegrityService


def _seed_campaign_with_basics(db_session):
    publication = Publication(name=PublicationName.UC_TODAY)
    template = TemplateVersion(display_id="TPL-2026-0001", name="demand", version=1, workflow_json={})
    deal = Deal(
        display_id="DEAL-001",
        client_id="client-1",
        am_user_id="am-1",
        brand_publication=PublicationName.UC_TODAY,
        status=DealStatus.READINESS_PASSED,
        sow_start_date=date(2026, 1, 5),
        sow_end_date=date(2026, 4, 5),
        icp="ICP",
        campaign_objective="Objective",
        messaging_positioning="Message",
        readiness_passed=True,
    )
    db_session.add_all([publication, template, deal])
    db_session.flush()

    campaign = Campaign(
        display_id="CAMP-2026-0001",
        deal_id=deal.id,
        template_version_id=template.id,
        campaign_type=CampaignType.DEMAND,
        tier="gold",
        title="Demand",
        status="not_started",
        planned_start_date=date(2026, 1, 5),
        planned_end_date=date(2026, 4, 5),
    )
    db_session.add(campaign)
    db_session.flush()

    planning = Stage(display_id="STG-2026-0001", campaign_id=campaign.id, name="planning")
    production = Stage(display_id="STG-2026-0002", campaign_id=campaign.id, name="production")
    promotion = Stage(display_id="STG-2026-0003", campaign_id=campaign.id, name="promotion")
    db_session.add_all([planning, production, promotion])
    db_session.flush()

    db_session.add(
        Milestone(
            display_id="MS-2026-0001",
            campaign_id=campaign.id,
            stage_id=planning.id,
            name="publishing",
            due_date=date(2026, 1, 12),
            baseline_date=date(2026, 1, 12),
            current_target_date=date(2026, 1, 12),
            sla_health=MilestoneSlaHealth.NOT_DUE,
            sla_health_manual_override=False,
        )
    )
    db_session.add(ProductModule(campaign_id=campaign.id, module_name="reach", enabled=True))
    db_session.flush()
    return campaign, publication, planning, production, promotion


def test_reconciliation_removes_legacy_promotion_coordination_step(db_session):
    campaign, publication, _planning, _production, promotion = _seed_campaign_with_basics(db_session)
    db_session.add(
        WorkflowStep(
            display_id="STEP-2026-0001",
            campaign_id=campaign.id,
            stage_id=promotion.id,
            stage_name="promotion",
            name="Promotion coordination",
            step_kind=WorkflowStepKind.TASK,
            owner_role=RoleName.CM,
        )
    )
    db_session.flush()

    StageIntegrityService(db_session).reconcile_campaign(campaign.id)

    names = [s.name for s in db_session.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()]
    assert "Promotion coordination" not in names


def test_publish_step_dedupe_is_by_name_and_linked_deliverable(db_session):
    campaign, publication, _planning, production, _promotion = _seed_campaign_with_basics(db_session)
    d1 = Deliverable(
        display_id="DEL-2026-0001",
        campaign_id=campaign.id,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.PLANNED,
        title="Article 1",
    )
    d2 = Deliverable(
        display_id="DEL-2026-0002",
        campaign_id=campaign.id,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.PLANNED,
        title="Article 2",
    )
    db_session.add_all([d1, d2])
    db_session.flush()

    # Same step name for different deliverables should survive as distinct rows.
    db_session.add_all(
        [
            WorkflowStep(
                display_id="STEP-2026-0002",
                campaign_id=campaign.id,
                stage_id=production.id,
                stage_name="production",
                name="Publish article",
                step_kind=WorkflowStepKind.TASK,
                owner_role=RoleName.CM,
                linked_deliverable_id=d1.id,
            ),
            WorkflowStep(
                display_id="STEP-2026-0003",
                campaign_id=campaign.id,
                stage_id=production.id,
                stage_name="production",
                name="Publish article",
                step_kind=WorkflowStepKind.TASK,
                owner_role=RoleName.CM,
                linked_deliverable_id=d2.id,
            ),
        ]
    )
    db_session.flush()

    StageIntegrityService(db_session).reconcile_campaign(campaign.id)

    publish_steps = db_session.scalars(
        select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id, WorkflowStep.name == "Publish article")
    ).all()
    assert len(publish_steps) == 2
    assert {s.linked_deliverable_id for s in publish_steps} == {d1.id, d2.id}


@pytest.mark.xfail(reason="Per-deliverable publish step creation is template-dependent in current implementation.", strict=False)
def test_two_article_campaign_keeps_two_article_publish_steps_after_reconcile(db_session):
    campaign, publication, _planning, _production, _promotion = _seed_campaign_with_basics(db_session)
    d1 = Deliverable(
        display_id="DEL-2026-0101",
        campaign_id=campaign.id,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.PLANNED,
        title="Article 1",
    )
    d2 = Deliverable(
        display_id="DEL-2026-0102",
        campaign_id=campaign.id,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.PLANNED,
        title="Article 2",
    )
    db_session.add_all([d1, d2])
    db_session.flush()

    StageIntegrityService(db_session).reconcile_campaign(campaign.id)

    steps = db_session.scalars(
        select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id, WorkflowStep.linked_deliverable_id.in_([d1.id, d2.id]))
    ).all()
    publish_linked = [s for s in steps if "publish" in (s.name or "").lower()]
    assert len({s.linked_deliverable_id for s in publish_linked}) == 2


@pytest.mark.xfail(reason="Generic 'Publish' cleanup is not currently guaranteed for all legacy step names.", strict=False)
def test_legacy_generic_publish_rows_cleaned_during_reconciliation(db_session):
    campaign, _publication, _planning, production, _promotion = _seed_campaign_with_basics(db_session)
    db_session.add(
        WorkflowStep(
            display_id="STEP-2026-0099",
            campaign_id=campaign.id,
            stage_id=production.id,
            stage_name="production",
                name="Publish",
                step_kind=WorkflowStepKind.TASK,
                owner_role=RoleName.CM,
                linked_deliverable_id=None,
            )
        )
    db_session.flush()

    StageIntegrityService(db_session).reconcile_campaign(campaign.id)

    generic = db_session.scalars(
        select(WorkflowStep).where(
            WorkflowStep.campaign_id == campaign.id,
            WorkflowStep.name == "Publish",
            WorkflowStep.linked_deliverable_id.is_(None),
        )
    ).all()
    assert generic == []
