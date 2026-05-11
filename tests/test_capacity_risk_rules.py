from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.domain import (
    Campaign,
    CampaignType,
    CapacityLedger,
    Deal,
    DealStatus,
    ManualRisk,
    PublicationName,
    RiskSeverity,
    RoleName,
    Stage,
    SystemRisk,
    WorkflowStep,
    WorkflowStepEffort,
    WorkflowStepKind,
)
from app.services.capacity_override_service import CapacityOverrideService
from app.services.ops_job_service import OpsJobService


def _seed_campaign_and_stage(db_session) -> tuple[Campaign, Stage]:
    deal = Deal(
        display_id="DEAL-CAP-1",
        client_id="client-1",
        am_user_id="am-1",
        brand_publication=PublicationName.UC_TODAY,
        status=DealStatus.READINESS_PASSED,
        icp="ICP",
        campaign_objective="Objective",
        messaging_positioning="Message",
        readiness_passed=True,
    )
    db_session.add(deal)
    db_session.flush()

    campaign = Campaign(
        display_id="CAMP-CAP-1",
        deal_id=deal.id,
        template_version_id="tpl-1",
        campaign_type=CampaignType.DEMAND,
        tier="gold",
        title="Capacity campaign",
    )
    db_session.add(campaign)
    db_session.flush()

    stage = Stage(display_id="STG-CAP-1", campaign_id=campaign.id, name="production")
    db_session.add(stage)
    db_session.flush()
    return campaign, stage


def test_capacity_warning_recorded_when_threshold_exceeded(db_session):
    campaign, stage = _seed_campaign_and_stage(db_session)
    step = WorkflowStep(
        display_id="STEP-CAP-1",
        campaign_id=campaign.id,
        stage_id=stage.id,
        stage_name="production",
        name="Heavy production task",
        step_kind=WorkflowStepKind.TASK,
        owner_role=RoleName.CM,
        planned_hours=0.0,
        planned_hours_baseline=0.0,
        planned_work_date=date(2026, 1, 5),
        next_owner_user_id="user-1",
    )
    db_session.add(step)
    db_session.flush()
    db_session.add(
        WorkflowStepEffort(
            display_id="EFF-CAP-1",
            workflow_step_id=step.id,
            role_name=RoleName.CM,
            hours=60.0,
            assigned_user_id="user-1",
        )
    )
    db_session.flush()

    summary = OpsJobService(db_session).run_all()

    assert summary.over_capacity_rows >= 1
    assert summary.system_risks_opened_or_updated >= 1
    assert db_session.scalars(select(SystemRisk)).all()


def test_capacity_override_request_and_decision_flow(db_session):
    row = CapacityLedger(
        display_id="CAP-2026-0001",
        user_id="user-1",
        role_name=RoleName.CM,
        week_start=date(2026, 1, 5),
        capacity_hours=20.0,
        planned_hours=32.0,
        active_planned_hours=0.0,
        forecast_planned_hours=32.0,
    )
    db_session.add(row)
    db_session.flush()

    service = CapacityOverrideService(db_session)
    service.request_override(row, "cm-1", "Temporary launch load")
    service.decide_override(row, "head-ops-1", True, "Approved for launch week")

    assert row.override_requested is True
    assert row.override_approved is True
    assert row.override_approved_by_user_id == "head-ops-1"


def test_system_and_manual_risks_stay_separate_channels(db_session):
    campaign, _stage = _seed_campaign_and_stage(db_session)
    system = SystemRisk(
        display_id="RSYS-1",
        campaign_id=campaign.id,
        risk_code="capacity_overload:user-1:cm:2026-01-05",
        severity=RiskSeverity.HIGH,
        details="Over capacity",
        is_open=True,
    )
    manual = ManualRisk(
        display_id="RMAN-1",
        campaign_id=campaign.id,
        raised_by_user_id="u-1",
        severity=RiskSeverity.MEDIUM,
        details="Client dependency",
        is_open=True,
    )
    db_session.add_all([system, manual])
    db_session.commit()

    stored_system = db_session.scalars(select(SystemRisk).where(SystemRisk.id == system.id)).one()
    stored_manual = db_session.scalars(select(ManualRisk).where(ManualRisk.id == manual.id)).one()

    assert stored_system.risk_code.startswith("capacity_overload")
    assert stored_manual.details == "Client dependency"


def test_manual_risk_updates_do_not_overwrite_system_risks(db_session):
    campaign, _stage = _seed_campaign_and_stage(db_session)
    system = SystemRisk(
        display_id="RSYS-2",
        campaign_id=campaign.id,
        risk_code="step_overdue:step-1",
        severity=RiskSeverity.HIGH,
        details="Step overdue",
        is_open=True,
    )
    manual = ManualRisk(
        display_id="RMAN-2",
        campaign_id=campaign.id,
        raised_by_user_id="u-1",
        severity=RiskSeverity.LOW,
        details="Initial note",
        is_open=True,
    )
    db_session.add_all([system, manual])
    db_session.commit()

    manual.details = "Updated mitigation details"
    manual.severity = RiskSeverity.MEDIUM
    db_session.commit()

    refreshed_system = db_session.get(SystemRisk, system.id)
    assert refreshed_system.details == "Step overdue"
    assert refreshed_system.severity == RiskSeverity.HIGH
