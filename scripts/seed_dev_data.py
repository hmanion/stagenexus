from __future__ import annotations

from app.db.session import SessionLocal
from app.seeds.bootstrap_seed import seed_bootstrap
from scripts.seed_reference_data import seed_reference_data


def main() -> None:
    seed_reference_data()
    with SessionLocal() as session:
        seed_bootstrap(session)
    print("Development seed data applied.")


if __name__ == "__main__":
    main()
