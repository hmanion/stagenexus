from __future__ import annotations

from app.core.config import settings
from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.seeds.bootstrap_seed import seed_bootstrap
from scripts.seed_reference_data import seed_reference_data


def main() -> None:
    if not settings.is_local_env:
        raise RuntimeError(
            "scripts/init_db.py is a local reset helper only. "
            "Use Alembic migrations in staging/production."
        )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_reference_data()
    with SessionLocal() as session:
        seed_bootstrap(session)
    print("Local database reset, schema recreated, and seed data loaded.")


if __name__ == "__main__":
    main()
