from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.models.domain import CampaignType, DeliverableStatus, DeliverableType, PublicationName, RoleName


def build_deal(**overrides):
    base = {
        "id": "deal-1",
        "display_id": "DEAL-001",
        "client_id": "client-1",
        "am_user_id": "am-1",
        "brand_publication": PublicationName.UC_TODAY,
        "status": "draft",
        "sow_start_date": date(2026, 1, 5),
        "sow_end_date": date(2026, 12, 31),
        "icp": "Global IT leaders",
        "campaign_objective": "Drive demand",
        "messaging_positioning": "Trusted advisory",
        "readiness_passed": False,
        "assigned_cm_user_id": None,
        "assigned_cc_user_id": None,
        "assigned_ccs_user_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def build_campaign(**overrides):
    base = {
        "id": "campaign-1",
        "display_id": "CAMP-001",
        "deal_id": "deal-1",
        "template_version_id": "tpl-1",
        "campaign_type": CampaignType.DEMAND,
        "tier": "gold",
        "title": "Demand campaign",
        "status": "not_started",
        "planned_start_date": date(2026, 1, 5),
        "planned_end_date": date(2026, 4, 4),
        "is_demand_sprint": True,
        "demand_sprint_number": 1,
        "demand_track": "create_reach",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def build_deliverable(**overrides):
    base = {
        "id": "deliverable-1",
        "display_id": "DEL-001",
        "campaign_id": "campaign-1",
        "title": "Article 1",
        "deliverable_type": DeliverableType.ARTICLE,
        "status": DeliverableStatus.APPROVED,
        "ready_to_publish_by_user_id": None,
        "ready_to_publish_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def build_workflow_step(**overrides):
    base = {
        "id": "step-1",
        "display_id": "STEP-001",
        "campaign_id": "campaign-1",
        "stage_id": "stage-1",
        "stage_name": "production",
        "name": "Publish article",
        "owner_role": RoleName.CM,
        "linked_deliverable_id": "deliverable-1",
        "normalized_status": "not_started",
        "current_start": date(2026, 1, 5),
        "current_due": date(2026, 1, 6),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def build_milestone(**overrides):
    base = {
        "id": "ms-1",
        "display_id": "MS-001",
        "campaign_id": "campaign-1",
        "name": "content_plan",
        "offset_days_from_campaign_start": 1,
        "due_date": date(2026, 1, 6),
        "current_target_date": date(2026, 1, 6),
        "baseline_date": date(2026, 1, 6),
        "completion_date": None,
        "achieved_at": None,
        "sla_health": "not_due",
        "sla_health_manual_override": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def build_capacity_ledger(**overrides):
    base = {
        "id": "cap-1",
        "display_id": "CAP-001",
        "user_id": "u-1",
        "role_name": RoleName.CM,
        "capacity_hours": 20.0,
        "planned_hours": 30.0,
        "override_requested": False,
        "override_approved": False,
        "override_reason": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def build_sow_change_request(**overrides):
    base = {
        "id": "sow-1",
        "display_id": "SOW-001",
        "campaign_id": "campaign-1",
        "requested_by_user_id": "u-requestor",
        "impact_scope_json": {"timeline": "+5 working days"},
        "status": "pending",
        "activated_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)
