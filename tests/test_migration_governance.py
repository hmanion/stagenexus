from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.db.migration_guard import assert_database_at_migration_head


class AlembicDiscoveryTests(unittest.TestCase):
    def test_single_head_is_discoverable(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        config = Config(str(project_root / "alembic.ini"))
        script_dir = ScriptDirectory.from_config(config)
        heads = script_dir.get_heads()

        self.assertEqual(len(heads), 1)
        self.assertEqual(heads[0], "219fcb44bea6")


class StartupGuardTests(unittest.TestCase):
    def test_startup_checks_alembic_head_when_compat_disabled_outside_local(self) -> None:
        from app import main

        fake_settings = SimpleNamespace(
            runtime_schema_compat=False,
            is_local_env=False,
            validate_for_environment=lambda: None,
            stage_steps_csv_path_resolved=SimpleNamespace(exists=lambda: True),
        )
        with (
            patch.object(main, "settings", fake_settings),
            patch.object(main, "assert_database_at_migration_head") as assert_head,
            patch.object(main, "assert_sqlite_foreign_keys_enabled") as assert_fk,
            patch.object(main, "assert_runtime_integrity") as assert_integrity,
            patch.object(main, "ensure_runtime_schema") as ensure_schema,
            patch.object(main.Base.metadata, "create_all") as create_all,
        ):
            main.startup()

        assert_head.assert_called_once()
        assert_fk.assert_called_once()
        assert_integrity.assert_called_once()
        ensure_schema.assert_not_called()
        create_all.assert_not_called()

    def test_startup_uses_runtime_compat_path_in_local(self) -> None:
        from app import main

        fake_settings = SimpleNamespace(
            runtime_schema_compat=True,
            is_local_env=True,
            validate_for_environment=lambda: None,
        )
        with (
            patch.object(main, "settings", fake_settings),
            patch.object(main, "assert_database_at_migration_head") as assert_head,
            patch.object(main, "assert_sqlite_foreign_keys_enabled") as assert_fk,
            patch.object(main, "assert_runtime_integrity") as assert_integrity,
            patch.object(main, "ensure_runtime_schema") as ensure_schema,
            patch.object(main.Base.metadata, "create_all") as create_all,
        ):
            main.startup()

        create_all.assert_called_once()
        ensure_schema.assert_called_once()
        assert_head.assert_not_called()
        assert_fk.assert_called_once()
        assert_integrity.assert_called_once()


class MigrationHeadGuardTests(unittest.TestCase):
    def test_guard_raises_when_alembic_version_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "missing_version.db"
            engine = create_engine(f"sqlite:///{db_path}", future=True)
            with self.assertRaises(RuntimeError) as exc:
                assert_database_at_migration_head(engine)
            self.assertIn("missing alembic_version", str(exc.exception))
            engine.dispose()

    def test_guard_raises_when_db_is_not_at_head(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        config = Config(str(project_root / "alembic.ini"))
        script_dir = ScriptDirectory.from_config(config)
        head = script_dir.get_current_head()
        wrong_revision = "000000000000" if head != "000000000000" else "111111111111"

        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "behind.db"
            engine = create_engine(f"sqlite:///{db_path}", future=True)
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
                conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": wrong_revision})

            with self.assertRaises(RuntimeError) as exc:
                assert_database_at_migration_head(engine)
            self.assertIn("not at Alembic head", str(exc.exception))
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
