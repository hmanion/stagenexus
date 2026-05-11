from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.db.session import SessionLocal
from app.seeds.reference_data import (
    load_stage_steps_from_validated_csv,
    upsert_stage_steps_reference,
)


@dataclass(frozen=True)
class SeedReferenceResult:
    action: str
    row_count: int
    source_csv_path: str


def seed_reference_data() -> SeedReferenceResult:
    csv_path = settings.stage_steps_csv_path_resolved
    rows = load_stage_steps_from_validated_csv(csv_path)
    with SessionLocal() as db:
        action = upsert_stage_steps_reference(
            db,
            rows=rows,
            source_csv_path=str(csv_path),
        )
        db.commit()
    return SeedReferenceResult(
        action=action,
        row_count=len(rows),
        source_csv_path=str(csv_path),
    )


def main() -> None:
    result = seed_reference_data()
    print(
        "Reference data seed complete: "
        f"action={result.action}, rows={result.row_count}, csv={result.source_csv_path}"
    )


if __name__ == "__main__":
    main()
