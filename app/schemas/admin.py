from __future__ import annotations

from pydantic import BaseModel, Field


class OpsDefaultsUpdateIn(BaseModel):
    capacity_hours_per_week: dict[str, float] = Field(default_factory=dict)
    timeline_defaults: dict[str, int] = Field(default_factory=dict)
    content_workload_hours: dict[str, float] = Field(default_factory=dict)
    health_buffer_days: dict[str, dict[str, int]] = Field(default_factory=dict)
    progress_segment_order: list[str] = Field(default_factory=list)
    card_module_config: dict[str, dict[str, bool]] = Field(default_factory=dict)
    card_module_bindings: dict[str, dict[str, str]] = Field(default_factory=dict)
    list_module_config: dict[str, dict[str, bool]] = Field(default_factory=dict)
    list_module_bindings: dict[str, dict[str, str]] = Field(default_factory=dict)


class RolePermissionsUpdateIn(BaseModel):
    role_flags: dict[str, dict[str, bool]] = Field(default_factory=dict)
    control_permissions: dict[str, list[str]] = Field(default_factory=dict)
    identity_permissions: dict[str, dict[str, dict[str, list[str]]]] = Field(default_factory=dict)


class AdminUserCreateIn(BaseModel):
    full_name: str
    email: str
    roles: list[str] = Field(default_factory=list)
    primary_team: str = "client_services"
    seniority: str = "standard"
    app_role: str = "user"


class AdminUserRolesUpdateIn(BaseModel):
    roles: list[str] = Field(default_factory=list)
    full_name: str | None = None
    email: str | None = None
    primary_team: str = "client_services"
    seniority: str = "standard"
    app_role: str = "user"
