from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import REPO_ROOT, settings
from app import models  # noqa: F401
from app.db.session import SessionLocal, engine
from app.seeds.bootstrap_seed import seed_bootstrap
from scripts.seed_reference_data import seed_reference_data


def _alembic_config() -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def _remove_sqlite_database_file() -> bool:
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return False

    database_path = Path(url.database)
    if not database_path.is_absolute():
        database_path = REPO_ROOT / database_path
    engine.dispose()
    database_path.unlink(missing_ok=True)
    return True


def _reset_schema_with_alembic() -> None:
    config = _alembic_config()
    if not _remove_sqlite_database_file():
        command.downgrade(config, "base")
    command.upgrade(config, "head")


def main() -> None:
    if not settings.is_local_env:
        raise RuntimeError(
            "scripts/init_db.py is a local reset helper only. "
            "Use Alembic migrations in staging/production."
        )
    _reset_schema_with_alembic()
    seed_reference_data()
    with SessionLocal() as session:
        seed_bootstrap(session)
    print("Local database reset via Alembic migrations and seed data loaded.")


if __name__ == "__main__":
    main()
