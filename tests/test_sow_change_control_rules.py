from __future__ import annotations

from sqlalchemy import select

from app.models.domain import ApprovalStatus, Campaign, CampaignType, Deal, DealStatus, PublicationName, RoleName, SowChangeApproval
from app.services.change_control_service import ChangeControlService


def _seed_campaign(db_session) -> Campaign:
    deal = Deal(
        display_id="DEAL-900",
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
        display_id="CAMP-900",
        deal_id=deal.id,
        template_version_id="tpl-1",
        campaign_type=CampaignType.DEMAND,
        tier="gold",
        title="Campaign",
    )
    db_session.add(campaign)
    db_session.flush()
    return campaign


def test_single_approval_does_not_activate_change_request(db_session):
    campaign = _seed_campaign(db_session)
    service = ChangeControlService(db_session)
    request = service.create_request(campaign.id, "requestor-1", {"timeline": "+5 working days"})
    db_session.flush()

    updated = service.apply_approval(request.display_id, "ops-1", RoleName.HEAD_OPS, "approved")

    assert updated.status == "pending"
    assert updated.activated_at is None


def test_two_required_approvals_activate_change_request(db_session):
    campaign = _seed_campaign(db_session)
    service = ChangeControlService(db_session)
    request = service.create_request(campaign.id, "requestor-1", {"timeline": "+5 working days"})
    db_session.flush()

    service.apply_approval(request.display_id, "ops-1", RoleName.HEAD_OPS, "approved")
    updated = service.apply_approval(request.display_id, "sales-1", RoleName.HEAD_SALES, "approved")

    assert updated.status == "activated"
    assert updated.activated_at is not None


def test_rejected_approval_prevents_activation(db_session):
    campaign = _seed_campaign(db_session)
    service = ChangeControlService(db_session)
    request = service.create_request(campaign.id, "requestor-1", {"timeline": "+5 working days"})
    db_session.flush()

    service.apply_approval(request.display_id, "ops-1", RoleName.HEAD_OPS, "approved")
    updated = service.apply_approval(request.display_id, "sales-1", RoleName.HEAD_SALES, "rejected")

    assert updated.status == "rejected"
    assert updated.activated_at is None


def test_invalid_approver_role_is_rejected(db_session):
    campaign = _seed_campaign(db_session)
    service = ChangeControlService(db_session)
    request = service.create_request(campaign.id, "requestor-1", {"timeline": "+5 working days"})

    try:
        service.apply_approval(request.display_id, "cc-1", RoleName.CC, "approved")
    except ValueError as exc:
        assert "Invalid approver role" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid approver role")


def test_timeline_impact_application_not_implemented_until_activation(db_session):
    campaign = _seed_campaign(db_session)
    service = ChangeControlService(db_session)
    request = service.create_request(campaign.id, "requestor-1", {"timeline": "+5 working days"})
    db_session.flush()

    approvals = db_session.scalars(
        select(SowChangeApproval).where(SowChangeApproval.sow_change_request_id == request.id)
    ).all()
    assert all(a.status == ApprovalStatus.PENDING for a in approvals)
    # Current boundary: timeline impact is stored on request payload and no timeline mutation service is invoked pre-activation.
    assert request.status == "pending"
