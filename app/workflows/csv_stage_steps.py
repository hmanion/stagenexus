from __future__ import annotations

import csv
from pathlib import Path

from app.models.domain import RoleName


CSV_PRODUCT_COLUMNS = {
    "demand_create": "Demand Create",
    "demand_reach": "Demand Reach",
    "demand_capture": "Demand Capture",
    "response": "Response",
    "amplify": "Amplify",
    "display": "Display",
}

ROLE_HOUR_COLUMNS = {
    RoleName.CC.value: "CC Hours",
    RoleName.CM.value: "CM Hours",
    RoleName.AM.value: "AM Hours",
    RoleName.DN.value: "DN hours",
    RoleName.MM.value: "MM Hours",
}


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _tier_filter(value: str) -> list[str]:
    raw = _norm(value).lower()
    if raw in {"", "na", "n/a"}:
        return []
    if raw == "all":
        return ["bronze", "silver", "gold"]
    if raw in {"silver, gold", "silver,gold"}:
        return ["silver", "gold"]
    if raw in {"gold"}:
        return ["gold"]
    if raw in {"silver"}:
        return ["silver"]
    if raw in {"bronze"}:
        return ["bronze"]
    return []


def _step_kind(raw_type: str) -> str:
    v = _norm(raw_type).lower()
    if v == "call":
        return "call"
    if v == "review":
        return "approval"
    return "task"


def _frequency(raw_value: str) -> str:
    v = _norm(raw_value).lower()
    if "piece of content" in v:
        return "per_content_piece"
    return "per_campaign"


def load_stage_steps_from_csv(csv_path: str) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        return []

    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            step_name = _norm(rec.get("Step"))
            stage_name = _norm(rec.get("Stage")).lower() or "production"
            if not step_name:
                continue

            hours_by_role: dict[str, float] = {}
            for role_key, col_name in ROLE_HOUR_COLUMNS.items():
                raw = _norm(rec.get(col_name))
                try:
                    hours = float(raw) if raw else 0.0
                except ValueError:
                    hours = 0.0
                if hours > 0:
                    hours_by_role[role_key] = hours

            applicability: dict[str, list[str]] = {}
            for product_key, col_name in CSV_PRODUCT_COLUMNS.items():
                applicability[product_key] = _tier_filter(_norm(rec.get(col_name)))

            deps = [
                part.strip()
                for part in _norm(rec.get("Dependent on?")).split(",")
                if part.strip()
            ]

            rows.append(
                {
                    "stage": stage_name,
                    "step_name": step_name,
                    "step_kind": _step_kind(_norm(rec.get("Type"))),
                    "hours_by_role": hours_by_role,
                    "applicability_by_product": applicability,
                    "frequency": _frequency(_norm(rec.get("How many?"))),
                    "dependencies": deps,
                    "notes": _norm(rec.get("Notes")),
                }
            )
    return rows
