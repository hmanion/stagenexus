from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.engine import Engine


def assert_database_at_migration_head(engine: Engine) -> None:
    """
    Fail fast when the connected database is not upgraded to Alembic head.

    This guard is intended for staging/production-style startup where runtime
    schema mutation is disabled.
    """
    alembic_cfg = Config(str(_project_root() / "alembic.ini"))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    expected_heads = set(script_dir.get_heads())

    with engine.connect() as conn:
        table_names = set(inspect(conn).get_table_names())
        if "alembic_version" not in table_names:
            raise RuntimeError(
                "Database is missing alembic_version. Run 'alembic upgrade head' before startup."
            )
        db_revisions = {
            str(row[0])
            for row in conn.execute(text("SELECT version_num FROM alembic_version"))
            if row[0] is not None
        }

    if db_revisions != expected_heads:
        raise RuntimeError(
            "Database migration state is not at Alembic head. "
            f"Expected {sorted(expected_heads)}, found {sorted(db_revisions)}. "
            "Run 'alembic upgrade head' before startup."
        )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]
