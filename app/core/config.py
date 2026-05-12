from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.getenv("APP_ENV", "local")
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_env: str = APP_ENV
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./campaign_ops.db")
    secret_key: str = os.getenv("SECRET_KEY", "change-me")
    runtime_schema_compat: bool = _as_bool(os.getenv("RUNTIME_SCHEMA_COMPAT"), False)
    holiday_source_url: str = os.getenv("HOLIDAY_SOURCE_URL", "https://www.gov.uk/bank-holidays.json")
    show_demo_rail: bool = _as_bool(os.getenv("SHOW_DEMO_RAIL"), True)
    demo_rail_allowed_roles: tuple[str, ...] = tuple(
        role.strip().lower()
        for role in os.getenv("DEMO_RAIL_ALLOWED_ROLES", "head_ops,admin").split(",")
        if role.strip()
    )
    working_week: tuple[str, ...] = tuple(
        day.strip().lower() for day in os.getenv("WORKING_WEEK", "mon,tue,wed,thu").split(",") if day.strip()
    )
    stage_steps_csv_path: str = os.getenv("STAGE_STEPS_CSV_PATH", "app/seeds/stage_steps_hours.csv")

    @property
    def is_local_env(self) -> bool:
        return self.app_env in {"local", "dev", "development"}

    @property
    def stage_steps_csv_path_resolved(self) -> Path:
        path = Path(self.stage_steps_csv_path)
        if path.is_absolute():
            return path
        return REPO_ROOT / path

    def validate_for_environment(self) -> None:
        if self.is_local_env:
            return

        if self.database_url.startswith("sqlite"):
            raise RuntimeError("DATABASE_URL must not use sqlite outside local/dev.")
        if self.secret_key in {"change-me", "replace-me", ""}:
            raise RuntimeError("SECRET_KEY must be explicitly configured outside local/dev.")
        if self.runtime_schema_compat:
            raise RuntimeError("RUNTIME_SCHEMA_COMPAT must be false outside local/dev.")
        if not self.working_week:
            raise RuntimeError("WORKING_WEEK must contain at least one day.")


settings = Settings()
