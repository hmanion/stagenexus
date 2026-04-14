from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import OpsDefaultConfig


APP_CONTROL_IDS: set[str] = {
    "run_ops_job",
    "refresh_data",
    "admin_add_user",
    "admin_edit_user_name",
    "admin_edit_user_email",
    "admin_set_user_team",
    "admin_set_user_seniority_manager",
    "admin_set_user_seniority_leadership",
    "admin_set_user_app_role_admin",
    "admin_set_user_app_role_superadmin",
    "admin_remove_user",
}


def _split_identity_control_permissions(legacy_rules: dict[str, Any]) -> tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, list[str]]]]:
    campaign_controls: dict[str, dict[str, list[str]]] = {}
    app_controls: dict[str, dict[str, list[str]]] = {}
    for control_id, raw_rule in (legacy_rules or {}).items():
        if not isinstance(raw_rule, dict):
            continue
        teams = [str(v) for v in (raw_rule.get("teams") or [])]
        seniorities = [str(v) for v in (raw_rule.get("seniorities") or [])]
        app_roles = [str(v) for v in (raw_rule.get("app_roles") or [])]
        if control_id in APP_CONTROL_IDS or str(control_id).startswith("admin_"):
            app_controls[control_id] = {
                "seniorities": seniorities,
                "app_roles": app_roles,
            }
        else:
            campaign_controls[control_id] = {
                "teams": teams,
                "seniorities": seniorities,
            }
    return campaign_controls, app_controls


def _ensure_identity_permission_split(payload: dict[str, Any]) -> None:
    identity_permissions = payload.setdefault("identity_permissions", {})
    if not isinstance(identity_permissions, dict):
        payload["identity_permissions"] = {}
        identity_permissions = payload["identity_permissions"]
    campaign_rules = identity_permissions.get("campaign_control_permissions")
    app_rules = identity_permissions.get("app_control_permissions")
    if isinstance(campaign_rules, dict) and isinstance(app_rules, dict):
        return
    legacy_rules = identity_permissions.get("control_permissions") or {}
    campaign_map, app_map = _split_identity_control_permissions(legacy_rules if isinstance(legacy_rules, dict) else {})
    identity_permissions["campaign_control_permissions"] = campaign_map
    identity_permissions["app_control_permissions"] = app_map


DEFAULTS: dict[str, Any] = {
    "capacity_hours_per_week": {
        "am": 8.0,
        "cm": 28.0,
        "cc": 16.0,
        "dn": 16.0,
        "mm": 16.0,
    },
    "timeline_defaults": {
        "interview_weeks_after_ko": 2,
        "writing_working_days": 8,
        "internal_review_working_days": 2,
        "client_review_working_days": 5,
        "publish_after_client_review_working_days": 1,
        "promotion_duration_calendar_days": 44,
        "reporting_duration_calendar_days": 14,
    },
    "content_workload_hours": {
        "ko_prep_hours": 2.0,
        "content_plan_hours": 2.0,
        "interview_hours": 1.5,
        "article_drafting_hours": 4.0,
        "video_brief_hours": 0.5,
        "amends_reserve_hours": 0.5,
    },
    "review_windows_working_days": {
        "internal": 2,
        "client": 5,
        "amends": 2,
    },
    "health_buffer_days": {
        "step": {"default": 3},
        "deliverable": {
            "not_started": 24,
            "planning": 20,
            "production": 12,
            "promotion": 8,
            "reporting": 8,
            "default": 12,
        },
        "campaign": {
            "not_started": 24,
            "planning": 20,
            "production": 12,
            "promotion": 8,
            "reporting": 8,
            "default": 12,
        },
        "scope": {"default": 24},
    },
    "progress_segment_order": [
        "done",
        "in_progress",
        "on_hold",
        "blocked_client",
        "blocked_internal",
        "blocked_dependency",
        "cancelled",
        "not_started",
    ],
    "card_module_config": {
        "scope": {
            "subtitle": True,
            "description": False,
            "progress": False,
            "key_values": True,
            "list": True,
            "tags": True,
            "status_badge": True,
            "avatar_stack": True,
            "due_date": True,
            "actions": True,
        },
        "campaign": {
            "subtitle": True,
            "description": False,
            "progress": True,
            "key_values": True,
            "list": True,
            "tags": True,
            "status_badge": True,
            "avatar_stack": True,
            "due_date": True,
            "actions": True,
        },
        "deliverable": {
            "subtitle": True,
            "description": False,
            "progress": False,
            "key_values": True,
            "list": False,
            "tags": True,
            "status_badge": True,
            "avatar_stack": True,
            "due_date": True,
            "actions": True,
        },
        "stage": {
            "subtitle": True,
            "description": False,
            "progress": True,
            "key_values": True,
            "list": True,
            "tags": True,
            "status_badge": True,
            "avatar_stack": False,
            "due_date": True,
            "actions": True,
        },
        "step": {
            "subtitle": True,
            "description": True,
            "progress": False,
            "key_values": True,
            "list": False,
            "tags": True,
            "status_badge": True,
            "avatar_stack": True,
            "due_date": True,
            "actions": True,
        },
    },
    "card_module_bindings": {
        "scope": {},
        "campaign": {},
        "deliverable": {},
        "stage": {},
        "step": {},
    },
    "list_module_config": {
        "scope": {
            "icon": True,
            "title": True,
            "plus_button": True,
            "type_tag": True,
            "progress": True,
            "status": True,
            "health": True,
            "owner": True,
            "avatars": True,
            "context_id": False,
            "options": True,
        },
        "campaign": {
            "icon": True,
            "title": True,
            "plus_button": True,
            "type_tag": True,
            "progress": True,
            "status": True,
            "health": True,
            "owner": True,
            "avatars": True,
            "context_id": True,
            "options": True,
        },
        "deliverable": {
            "icon": True,
            "title": True,
            "plus_button": False,
            "type_tag": True,
            "progress": False,
            "status": True,
            "health": False,
            "owner": True,
            "avatars": True,
            "context_id": True,
            "options": True,
        },
        "stage": {
            "icon": True,
            "title": True,
            "plus_button": True,
            "type_tag": True,
            "progress": True,
            "status": True,
            "health": True,
            "owner": False,
            "avatars": False,
            "context_id": True,
            "options": True,
        },
        "step": {
            "icon": True,
            "title": True,
            "plus_button": False,
            "type_tag": True,
            "progress": False,
            "status": True,
            "health": True,
            "owner": True,
            "avatars": True,
            "context_id": True,
            "options": True,
        },
    },
    "list_module_bindings": {
        "scope": {},
        "campaign": {},
        "deliverable": {},
        "stage": {},
        "step": {},
    },
    "role_permissions": {
        "role_flags": {
            "am": {
                "show_deals_pipeline": True,
                "show_capacity": False,
                "show_risks": True,
                "show_reviews": True,
                "show_admin": False,
            },
            "head_ops": {
                "show_deals_pipeline": True,
                "show_capacity": True,
                "show_risks": True,
                "show_reviews": True,
                "show_admin": True,
            },
            "cm": {
                "show_deals_pipeline": False,
                "show_capacity": True,
                "show_risks": True,
                "show_reviews": True,
                "show_admin": False,
            },
            "cc": {
                "show_deals_pipeline": False,
                "show_capacity": False,
                "show_risks": False,
                "show_reviews": True,
                "show_admin": False,
            },
            "ccs": {
                "show_deals_pipeline": False,
                "show_capacity": False,
                "show_risks": False,
                "show_reviews": True,
                "show_admin": False,
            },
            "dn": {
                "show_deals_pipeline": False,
                "show_capacity": False,
                "show_risks": False,
                "show_reviews": False,
                "show_admin": False,
            },
            "mm": {
                "show_deals_pipeline": False,
                "show_capacity": False,
                "show_risks": False,
                "show_reviews": False,
                "show_admin": False,
            },
            "admin": {
                "show_deals_pipeline": True,
                "show_capacity": True,
                "show_risks": True,
                "show_reviews": True,
                "show_admin": True,
            },
            "leadership_viewer": {
                "show_deals_pipeline": True,
                "show_capacity": True,
                "show_risks": True,
                "show_reviews": True,
                "show_admin": False,
            },
            "head_sales": {
                "show_deals_pipeline": True,
                "show_capacity": False,
                "show_risks": True,
                "show_reviews": False,
                "show_admin": False,
            },
            "client": {
                "show_deals_pipeline": False,
                "show_capacity": False,
                "show_risks": False,
                "show_reviews": True,
                "show_admin": False,
            },
        },
        "control_permissions": {
            "create_deal": ["am", "admin"],
            "create_submit_deal": ["am", "admin"],
            "create_demo_deal": ["am", "admin"],
            "submit_latest_deal": ["am", "admin"],
            "ops_approve_latest_deal": ["head_ops", "head_sales", "admin"],
            "generate_latest_campaigns": ["head_ops", "admin"],
            "complete_next_step": ["cm", "cc", "ccs", "head_ops", "admin"],
            "override_step_due": ["cm", "head_ops", "admin"],
            "run_ops_job": ["head_ops", "admin"],
            "mark_ready_publish": ["cm", "cc", "admin"],
            "run_sow_change": ["cm", "am", "head_ops", "head_sales", "admin"],
            "request_override": ["cm", "head_ops", "admin"],
            "approve_override": ["head_ops", "admin"],
            "refresh_data": ["am", "cm", "cc", "ccs", "head_ops", "head_sales", "admin"],
            "advance_deliverable": ["am", "cm", "cc", "head_ops", "admin"],
            "create_manual_risk": ["am", "cm", "head_ops", "admin"],
            "resolve_manual_risk": ["cm", "head_ops", "admin"],
            "resolve_escalation": ["head_ops", "admin"],
            "manage_step": ["cm", "cc", "ccs", "head_ops", "admin"],
            "manage_deliverable_owner": ["cm", "head_ops", "admin"],
            "manage_step_dates": ["cm", "head_ops", "admin"],
            "manage_deliverable_dates": ["cm", "head_ops", "admin"],
            "edit_deliverable_stage": ["cm", "head_ops", "admin"],
            "manage_campaign_assignments": ["head_ops", "admin"],
            "manage_campaign_status": ["cm", "head_ops", "admin"],
            "manage_campaign_dates": ["cm", "head_ops", "admin"],
            "delete_campaign": ["head_ops", "admin"],
            "delete_deliverable": ["head_ops", "admin"],
            "admin_add_user": ["admin"],
            "admin_edit_user_name": ["admin"],
            "admin_edit_user_email": ["admin"],
            "admin_set_user_team": ["admin"],
            "admin_set_user_seniority_manager": ["admin"],
            "admin_set_user_seniority_leadership": [],
            "admin_set_user_app_role_admin": [],
            "admin_set_user_app_role_superadmin": [],
            "admin_remove_user": [],
        },
    },
    "identity_permissions": {
        "screen_flags": {
            "show_deals_pipeline": {
                "teams": ["sales", "client_services"],
                "seniorities": ["standard", "manager", "leadership"],
                "app_roles": ["user", "admin", "superadmin"],
            },
            "show_capacity": {
                "teams": ["client_services"],
                "seniorities": ["standard", "manager", "leadership"],
                "app_roles": ["user", "admin", "superadmin"],
            },
            "show_risks": {
                "teams": ["sales", "client_services"],
                "seniorities": ["standard", "manager", "leadership"],
                "app_roles": ["user", "admin", "superadmin"],
            },
            "show_reviews": {
                "teams": ["sales", "editorial", "client_services"],
                "seniorities": ["standard", "manager", "leadership"],
                "app_roles": ["user", "admin", "superadmin"],
            },
            "show_admin": {
                "teams": ["sales", "editorial", "marketing", "client_services"],
                "seniorities": ["standard", "manager", "leadership"],
                "app_roles": ["admin", "superadmin"],
            },
        },
        "control_permissions": {
            "create_deal": {"teams": ["sales"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "create_submit_deal": {"teams": ["sales"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "create_demo_deal": {"teams": ["sales"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "submit_latest_deal": {"teams": ["sales"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "ops_approve_latest_deal": {"teams": ["sales", "client_services"], "seniorities": ["leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "generate_latest_campaigns": {"teams": ["client_services"], "seniorities": ["leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "complete_next_step": {"teams": ["editorial", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "override_step_due": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "run_ops_job": {"teams": ["client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "mark_ready_publish": {"teams": ["editorial", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "run_sow_change": {"teams": ["sales", "client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "request_override": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "approve_override": {"teams": ["client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "refresh_data": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "advance_deliverable": {"teams": ["sales", "editorial", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "create_manual_risk": {"teams": ["sales", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "resolve_manual_risk": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "resolve_escalation": {"teams": ["client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_step": {"teams": ["editorial", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_deliverable_owner": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_step_dates": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_deliverable_dates": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "edit_deliverable_stage": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_campaign_assignments": {"teams": ["client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_campaign_status": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "manage_campaign_dates": {"teams": ["client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "delete_campaign": {"teams": ["client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "delete_deliverable": {"teams": ["client_services"], "seniorities": ["manager", "leadership"], "app_roles": ["user", "admin", "superadmin"]},
            "admin_add_user": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["admin", "superadmin"]},
            "admin_edit_user_name": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["admin", "superadmin"]},
            "admin_edit_user_email": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["admin", "superadmin"]},
            "admin_set_user_team": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["admin", "superadmin"]},
            "admin_set_user_seniority_manager": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["admin", "superadmin"]},
            "admin_set_user_seniority_leadership": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["superadmin"]},
            "admin_set_user_app_role_admin": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["superadmin"]},
            "admin_set_user_app_role_superadmin": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["superadmin"]},
            "admin_remove_user": {"teams": ["sales", "editorial", "marketing", "client_services"], "seniorities": ["standard", "manager", "leadership"], "app_roles": ["superadmin"]},
        },
    },
}

_ensure_identity_permission_split(DEFAULTS)


class OpsDefaultsService:
    CONFIG_KEY = "global"

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> dict[str, Any]:
        row = self._row()
        if not row:
            payload = deepcopy(DEFAULTS)
            _ensure_identity_permission_split(payload)
            return payload
        merged = deepcopy(DEFAULTS)
        payload = row.config_json or {}
        self._deep_merge(merged, payload)
        _ensure_identity_permission_split(merged)
        return merged

    def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get()
        self._deep_merge(current, payload or {})
        _ensure_identity_permission_split(current)
        self._validate(current)

        row = self._row()
        if not row:
            row = OpsDefaultConfig(config_key=self.CONFIG_KEY, config_json=current)
            self.db.add(row)
        else:
            row.config_json = current
        self.db.flush()
        return current

    def _row(self) -> OpsDefaultConfig | None:
        return self.db.scalar(select(OpsDefaultConfig).where(OpsDefaultConfig.config_key == self.CONFIG_KEY))

    @staticmethod
    def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in (patch or {}).items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                OpsDefaultsService._deep_merge(target[key], value)
            else:
                target[key] = value

    @staticmethod
    def _validate(payload: dict[str, Any]) -> None:
        cap = payload.get("capacity_hours_per_week") or {}
        for role in ("am", "cm", "cc", "dn", "mm"):
            if role not in cap:
                raise ValueError(f"missing capacity role: {role}")
            value = float(cap[role])
            if value <= 0 or value > 80:
                raise ValueError(f"capacity {role} must be > 0 and <= 80")

        timeline = payload.get("timeline_defaults") or {}
        required = {
            "interview_weeks_after_ko": (1, 8),
            "writing_working_days": (1, 40),
            "internal_review_working_days": (1, 20),
            "client_review_working_days": (1, 30),
            "publish_after_client_review_working_days": (0, 10),
            "promotion_duration_calendar_days": (1, 120),
            "reporting_duration_calendar_days": (1, 60),
        }
        for key, (min_v, max_v) in required.items():
            if key not in timeline:
                raise ValueError(f"missing timeline default: {key}")
            value = int(timeline[key])
            if value < min_v or value > max_v:
                raise ValueError(f"{key} must be between {min_v} and {max_v}")

        workload = payload.get("content_workload_hours") or {}
        workload_required = (
            "ko_prep_hours",
            "content_plan_hours",
            "interview_hours",
            "article_drafting_hours",
            "video_brief_hours",
            "amends_reserve_hours",
        )
        for key in workload_required:
            if key not in workload:
                raise ValueError(f"missing workload default: {key}")
            value = float(workload[key])
            if value < 0 or value > 24:
                raise ValueError(f"{key} must be between 0 and 24")

        windows = payload.get("review_windows_working_days") or {}
        for key in ("internal", "client", "amends"):
            if key not in windows:
                raise ValueError(f"missing review window default: {key}")
            value = int(windows[key])
            if value < 1 or value > 30:
                raise ValueError(f"review_windows_working_days.{key} must be between 1 and 30")

        health_buffers = payload.get("health_buffer_days") or {}
        if not isinstance(health_buffers, dict):
            raise ValueError("health_buffer_days must be a mapping")
        for object_key in ("step", "deliverable", "campaign", "scope"):
            obj = health_buffers.get(object_key)
            if not isinstance(obj, dict):
                raise ValueError(f"health_buffer_days.{object_key} must be a mapping")
            for key, raw in obj.items():
                try:
                    value = int(raw)
                except Exception as exc:
                    raise ValueError(f"health_buffer_days.{object_key}.{key} must be an integer") from exc
                if value < 0 or value > 90:
                    raise ValueError(f"health_buffer_days.{object_key}.{key} must be between 0 and 90")

        progress_segment_order = payload.get("progress_segment_order") or []
        if not isinstance(progress_segment_order, list):
            raise ValueError("progress_segment_order must be a list")
        allowed_progress_states = {
            "done",
            "in_progress",
            "on_hold",
            "blocked_client",
            "blocked_internal",
            "blocked_dependency",
            "cancelled",
            "not_started",
        }
        normalized_progress = [str(v).strip().lower() for v in progress_segment_order]
        if len(set(normalized_progress)) != len(normalized_progress):
            raise ValueError("progress_segment_order cannot contain duplicate statuses")
        invalid_progress = [v for v in normalized_progress if v not in allowed_progress_states]
        if invalid_progress:
            raise ValueError(f"progress_segment_order has invalid statuses: {', '.join(sorted(set(invalid_progress)))}")

        card_module_cfg = payload.get("card_module_config") or {}
        if not isinstance(card_module_cfg, dict):
            raise ValueError("card_module_config must be a mapping")
        valid_modules = {"scope", "campaign", "deliverable", "stage", "step"}
        for module_key, module_cfg in card_module_cfg.items():
            if module_key not in valid_modules:
                raise ValueError(f"card_module_config.{module_key} is not a valid module")
            if not isinstance(module_cfg, dict):
                raise ValueError(f"card_module_config.{module_key} must be a mapping")
            for field_key, enabled in module_cfg.items():
                if not isinstance(field_key, str) or not field_key.strip():
                    raise ValueError(f"card_module_config.{module_key} contains an invalid field key")
                if not isinstance(enabled, bool):
                    raise ValueError(f"card_module_config.{module_key}.{field_key} must be boolean")

        card_module_bindings = payload.get("card_module_bindings") or {}
        if not isinstance(card_module_bindings, dict):
            raise ValueError("card_module_bindings must be a mapping")
        for module_key, module_bindings in card_module_bindings.items():
            if module_key not in valid_modules:
                raise ValueError(f"card_module_bindings.{module_key} is not a valid module")
            if not isinstance(module_bindings, dict):
                raise ValueError(f"card_module_bindings.{module_key} must be a mapping")
            for element_key, source_key in module_bindings.items():
                if not isinstance(element_key, str) or not element_key.strip():
                    raise ValueError(f"card_module_bindings.{module_key} contains an invalid element key")
                if not isinstance(source_key, str):
                    raise ValueError(f"card_module_bindings.{module_key}.{element_key} must be a string")

        list_module_cfg = payload.get("list_module_config") or {}
        if not isinstance(list_module_cfg, dict):
            raise ValueError("list_module_config must be a mapping")
        for module_key, module_cfg in list_module_cfg.items():
            if module_key not in valid_modules:
                raise ValueError(f"list_module_config.{module_key} is not a valid module")
            if not isinstance(module_cfg, dict):
                raise ValueError(f"list_module_config.{module_key} must be a mapping")
            for field_key, enabled in module_cfg.items():
                if not isinstance(field_key, str) or not field_key.strip():
                    raise ValueError(f"list_module_config.{module_key} contains an invalid field key")
                if not isinstance(enabled, bool):
                    raise ValueError(f"list_module_config.{module_key}.{field_key} must be boolean")

        list_module_bindings = payload.get("list_module_bindings") or {}
        if not isinstance(list_module_bindings, dict):
            raise ValueError("list_module_bindings must be a mapping")
        for module_key, module_bindings in list_module_bindings.items():
            if module_key not in valid_modules:
                raise ValueError(f"list_module_bindings.{module_key} is not a valid module")
            if not isinstance(module_bindings, dict):
                raise ValueError(f"list_module_bindings.{module_key} must be a mapping")
            for element_key, source_key in module_bindings.items():
                if not isinstance(element_key, str) or not element_key.strip():
                    raise ValueError(f"list_module_bindings.{module_key} contains an invalid element key")
                if not isinstance(source_key, str):
                    raise ValueError(f"list_module_bindings.{module_key}.{element_key} must be a string")

        role_permissions = payload.get("role_permissions") or {}
        role_flags = role_permissions.get("role_flags") or {}
        control_permissions = role_permissions.get("control_permissions") or {}
        if not isinstance(role_flags, dict):
            raise ValueError("role_permissions.role_flags must be a mapping")
        if not isinstance(control_permissions, dict):
            raise ValueError("role_permissions.control_permissions must be a mapping")

        valid_roles = {
            "am",
            "head_ops",
            "cm",
            "cc",
            "ccs",
            "dn",
            "mm",
            "admin",
            "leadership_viewer",
            "head_sales",
            "client",
        }
        required_flags = {"show_deals_pipeline", "show_capacity", "show_risks", "show_reviews", "show_admin"}

        for role, flags in role_flags.items():
            if role not in valid_roles:
                raise ValueError(f"invalid role key in role_flags: {role}")
            if not isinstance(flags, dict):
                raise ValueError(f"role_flags[{role}] must be a mapping")
            missing = required_flags.difference(flags.keys())
            if missing:
                raise ValueError(f"role_flags[{role}] missing flags: {', '.join(sorted(missing))}")
            for k, v in flags.items():
                if k not in required_flags:
                    raise ValueError(f"invalid role flag key: {k}")
                if not isinstance(v, bool):
                    raise ValueError(f"role_flags[{role}][{k}] must be boolean")
        if role_flags.get("head_ops", {}).get("show_admin") is not True:
            raise ValueError("head_ops must retain show_admin access")
        if role_flags.get("admin", {}).get("show_admin") is not True:
            raise ValueError("admin must retain show_admin access")

        for control_id, roles in control_permissions.items():
            if not isinstance(roles, list):
                raise ValueError(f"control_permissions[{control_id}] must be a list")
            invalid = [r for r in roles if r not in valid_roles]
            if invalid:
                raise ValueError(f"control_permissions[{control_id}] has invalid roles: {', '.join(invalid)}")

        identity_permissions = payload.get("identity_permissions") or {}
        if not isinstance(identity_permissions, dict):
            raise ValueError("identity_permissions must be a mapping")
        valid_teams = {"sales", "editorial", "marketing", "client_services"}
        valid_seniorities = {"standard", "manager", "leadership"}
        valid_app_roles = {"user", "admin", "superadmin"}

        def _validate_rule(rule: Any, path: str) -> None:
            if not isinstance(rule, dict):
                raise ValueError(f"{path} must be an object")
            teams = rule.get("teams")
            seniorities = rule.get("seniorities")
            app_roles = rule.get("app_roles")
            if not isinstance(teams, list) or not isinstance(seniorities, list) or not isinstance(app_roles, list):
                raise ValueError(f"{path} must include teams/seniorities/app_roles lists")
            bad_teams = [x for x in teams if x not in valid_teams]
            bad_seniorities = [x for x in seniorities if x not in valid_seniorities]
            bad_app_roles = [x for x in app_roles if x not in valid_app_roles]
            if bad_teams:
                raise ValueError(f"{path}.teams invalid values: {', '.join(sorted(set(bad_teams)))}")
            if bad_seniorities:
                raise ValueError(f"{path}.seniorities invalid values: {', '.join(sorted(set(bad_seniorities)))}")
            if bad_app_roles:
                raise ValueError(f"{path}.app_roles invalid values: {', '.join(sorted(set(bad_app_roles)))}")

        def _validate_campaign_control_rule(rule: Any, path: str) -> None:
            if not isinstance(rule, dict):
                raise ValueError(f"{path} must be an object")
            teams = rule.get("teams")
            seniorities = rule.get("seniorities")
            if not isinstance(teams, list) or not isinstance(seniorities, list):
                raise ValueError(f"{path} must include teams/seniorities lists")
            bad_teams = [x for x in teams if x not in valid_teams]
            bad_seniorities = [x for x in seniorities if x not in valid_seniorities]
            if bad_teams:
                raise ValueError(f"{path}.teams invalid values: {', '.join(sorted(set(bad_teams)))}")
            if bad_seniorities:
                raise ValueError(f"{path}.seniorities invalid values: {', '.join(sorted(set(bad_seniorities)))}")

        def _validate_app_control_rule(rule: Any, path: str) -> None:
            if not isinstance(rule, dict):
                raise ValueError(f"{path} must be an object")
            seniorities = rule.get("seniorities")
            app_roles = rule.get("app_roles")
            if not isinstance(seniorities, list) or not isinstance(app_roles, list):
                raise ValueError(f"{path} must include seniorities/app_roles lists")
            bad_seniorities = [x for x in seniorities if x not in valid_seniorities]
            bad_app_roles = [x for x in app_roles if x not in valid_app_roles]
            if bad_seniorities:
                raise ValueError(f"{path}.seniorities invalid values: {', '.join(sorted(set(bad_seniorities)))}")
            if bad_app_roles:
                raise ValueError(f"{path}.app_roles invalid values: {', '.join(sorted(set(bad_app_roles)))}")

        screen_rules = identity_permissions.get("screen_flags") or {}
        legacy_control_rules = identity_permissions.get("control_permissions") or {}
        campaign_control_rules = identity_permissions.get("campaign_control_permissions") or {}
        app_control_rules = identity_permissions.get("app_control_permissions") or {}
        if not isinstance(screen_rules, dict):
            raise ValueError("identity_permissions.screen_flags must be a mapping")
        if not isinstance(legacy_control_rules, dict):
            raise ValueError("identity_permissions.control_permissions must be a mapping")
        if not isinstance(campaign_control_rules, dict):
            raise ValueError("identity_permissions.campaign_control_permissions must be a mapping")
        if not isinstance(app_control_rules, dict):
            raise ValueError("identity_permissions.app_control_permissions must be a mapping")
        for key, rule in screen_rules.items():
            _validate_rule(rule, f"identity_permissions.screen_flags.{key}")
        for key, rule in legacy_control_rules.items():
            _validate_rule(rule, f"identity_permissions.control_permissions.{key}")
        for key, rule in campaign_control_rules.items():
            _validate_campaign_control_rule(rule, f"identity_permissions.campaign_control_permissions.{key}")
        for key, rule in app_control_rules.items():
            _validate_app_control_rule(rule, f"identity_permissions.app_control_permissions.{key}")
