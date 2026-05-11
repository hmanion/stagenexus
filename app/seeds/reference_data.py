from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import OpsDefaultConfig
from app.workflows.csv_stage_steps import (
    CSV_PRODUCT_COLUMNS,
    ROLE_HOUR_COLUMNS,
    load_stage_steps_from_csv,
)


STAGE_STEPS_REFERENCE_KEY = "stage_steps_reference"
STAGE_STEPS_REQUIRED_COLUMNS = {
    "Step",
    "Stage",
    "Type",
    "How many?",
    "Dependent on?",
    "Notes",
    *ROLE_HOUR_COLUMNS.values(),
    *CSV_PRODUCT_COLUMNS.values(),
}


def _read_csv_fieldnames(csv_path: Path) -> list[str]:
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            return list(reader.fieldnames or [])
    except csv.Error as exc:
        raise RuntimeError(f"Malformed CSV at {csv_path}: {exc}") from exc


def validate_stage_steps_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        raise RuntimeError(f"Stage steps CSV not found: {csv_path}")
    columns = set(_read_csv_fieldnames(csv_path))
    missing = sorted(STAGE_STEPS_REQUIRED_COLUMNS - columns)
    if missing:
        raise RuntimeError(
            "Stage steps CSV is missing required columns: " + ", ".join(missing)
        )


def load_stage_steps_from_validated_csv(csv_path: Path) -> list[dict]:
    validate_stage_steps_csv(csv_path)
    rows = load_stage_steps_from_csv(str(csv_path))
    if not rows:
        raise RuntimeError(f"Stage steps CSV contained no usable rows: {csv_path}")
    return rows


def _normalize_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("stage", "")),
            str(row.get("step_name", "")),
            str(row.get("step_kind", "")),
        ),
    )


def upsert_stage_steps_reference(
    db: Session, *, rows: list[dict], source_csv_path: str
) -> str:
    normalized_new = _normalize_rows(rows)
    config = db.scalar(
        select(OpsDefaultConfig).where(
            OpsDefaultConfig.config_key == STAGE_STEPS_REFERENCE_KEY
        )
    )
    if not config:
        db.add(
            OpsDefaultConfig(
                config_key=STAGE_STEPS_REFERENCE_KEY,
                config_json={
                    "rows": normalized_new,
                    "source_csv_path": source_csv_path,
                },
            )
        )
        return "added"

    current_rows = list((config.config_json or {}).get("rows") or [])
    normalized_current = _normalize_rows(current_rows)
    if normalized_current == normalized_new:
        return "skipped"

    config.config_json = {
        "rows": normalized_new,
        "source_csv_path": source_csv_path,
    }
    return "updated"


def get_stage_steps_from_db(db: Session) -> list[dict]:
    config = db.scalar(
        select(OpsDefaultConfig).where(
            OpsDefaultConfig.config_key == STAGE_STEPS_REFERENCE_KEY
        )
    )
    if not config:
        return []
    return list((config.config_json or {}).get("rows") or [])


def resolve_stage_steps_rows_for_bootstrap(db: Session) -> list[dict]:
    db_rows = get_stage_steps_from_db(db)
    if db_rows:
        return db_rows
    csv_path = settings.stage_steps_csv_path_resolved
    return load_stage_steps_from_validated_csv(csv_path)
