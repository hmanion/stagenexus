from __future__ import annotations

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.seeds.bootstrap_seed import seed_bootstrap


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_bootstrap(session)
    print("Database initialized and seeded.")


if __name__ == "__main__":
    main()
