from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.config import Settings
from app.core import config as app_config
from app.db.base import Base
from app.db.migration_guard import assert_database_at_migration_head
from app import models  # noqa: F401


class AlembicDiscoveryTests(unittest.TestCase):
    def test_single_head_is_discoverable(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        config = Config(str(project_root / "alembic.ini"))
        script_dir = ScriptDirectory.from_config(config)
        heads = script_dir.get_heads()

        self.assertEqual(len(heads), 1)
        self.assertEqual(heads[0], "c4a9f1e2b8d3")

    def test_fresh_database_upgraded_to_head_matches_model_columns(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "fresh_head.db"
            database_url = f"sqlite:///{db_path}"
            config = Config(str(project_root / "alembic.ini"))
            patched_settings = replace(
                app_config.settings,
                app_env="local",
                database_url=database_url,
                runtime_schema_compat=False,
            )

            with patch.object(app_config, "settings", patched_settings):
                command.upgrade(config, "head")

            engine = create_engine(database_url, future=True)
            inspector = inspect(engine)
            db_tables = set(inspector.get_table_names()) - {"alembic_version"}
            model_tables = set(Base.metadata.tables)

            self.assertEqual(model_tables - db_tables, set())
            self.assertEqual(db_tables - model_tables, set())

            for table_name in sorted(model_tables):
                db_columns = {column["name"] for column in inspector.get_columns(table_name)}
                model_columns = set(Base.metadata.tables[table_name].columns.keys())
                self.assertEqual(
                    db_columns,
                    model_columns,
                    f"{table_name} columns differ",
                )
            engine.dispose()


class StartupGuardTests(unittest.TestCase):
    def test_startup_checks_alembic_head_when_compat_disabled_in_any_environment(self) -> None:
        from app import main

        fake_settings = SimpleNamespace(
            runtime_schema_compat=False,
            is_local_env=True,
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

    def test_runtime_schema_compat_defaults_off_for_local(self) -> None:
        self.assertFalse(Settings(app_env="local").runtime_schema_compat)


class InitDbMigrationResetTests(unittest.TestCase):
    def test_init_db_resets_schema_with_alembic_not_metadata_create_all(self) -> None:
        from scripts import init_db

        fake_settings = SimpleNamespace(is_local_env=True)
        fake_session = unittest.mock.MagicMock()
        fake_session_factory = unittest.mock.MagicMock(return_value=fake_session)
        with (
            patch.object(init_db, "settings", fake_settings),
            patch.object(init_db, "_reset_schema_with_alembic") as reset_schema,
            patch.object(init_db, "seed_reference_data") as seed_reference,
            patch.object(init_db, "SessionLocal", fake_session_factory),
            patch.object(init_db, "seed_bootstrap") as seed_bootstrap,
            patch.object(Base.metadata, "create_all") as create_all,
        ):
            init_db.main()

        reset_schema.assert_called_once()
        create_all.assert_not_called()
        seed_reference.assert_called_once()
        seed_bootstrap.assert_called_once_with(fake_session.__enter__.return_value)


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
