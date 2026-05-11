from __future__ import annotations

from pathlib import Path
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.models.domain import OpsDefaultConfig
from app.seeds.reference_data import (
    STAGE_STEPS_REFERENCE_KEY,
    load_stage_steps_from_validated_csv,
    upsert_stage_steps_reference,
)


class ReferenceDataSeedTests(unittest.TestCase):
    def test_settings_default_stage_steps_path_not_personal_desktop(self) -> None:
        settings = Settings()
        self.assertNotIn("/Users/", settings.stage_steps_csv_path)
        self.assertNotIn("Desktop", settings.stage_steps_csv_path)

    def test_seed_loader_parses_bundled_csv(self) -> None:
        csv_path = Path("app/seeds/stage_steps_hours.csv")
        rows = load_stage_steps_from_validated_csv(csv_path)
        self.assertTrue(rows)
        self.assertTrue(all("step_name" in row for row in rows))

    def test_seed_loader_fails_on_missing_required_columns(self) -> None:
        tmp_dir = Path("tests/.tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        bad_csv = tmp_dir / "bad_stage_steps.csv"
        bad_csv.write_text("Step,Stage\nOnly step,planning\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "missing required columns"):
            load_stage_steps_from_validated_csv(bad_csv)
        bad_csv.unlink(missing_ok=True)

    def test_upsert_stage_steps_reference_is_idempotent(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=engine)
        rows = load_stage_steps_from_validated_csv(
            Path("app/seeds/stage_steps_hours.csv")
        )

        with Session(engine) as session:
            first_action = upsert_stage_steps_reference(
                session, rows=rows, source_csv_path="app/seeds/stage_steps_hours.csv"
            )
            session.commit()

            second_action = upsert_stage_steps_reference(
                session, rows=rows, source_csv_path="app/seeds/stage_steps_hours.csv"
            )
            session.commit()

            stored = (
                session.query(OpsDefaultConfig)
                .filter_by(config_key=STAGE_STEPS_REFERENCE_KEY)
                .one()
            )

        self.assertEqual(first_action, "added")
        self.assertEqual(second_action, "skipped")
        self.assertEqual(len(stored.config_json["rows"]), len(rows))

if __name__ == "__main__":
    unittest.main()
