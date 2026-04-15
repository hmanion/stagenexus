from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _set_sqlite_fk_pragma(dbapi_connection, _connection_record) -> None:
    if engine.url.get_backend_name() != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def assert_sqlite_foreign_keys_enabled(target_engine: Engine) -> None:
    if target_engine.url.get_backend_name() != "sqlite":
        return
    with target_engine.connect() as conn:
        # Defensive startup guard: enforce FK pragma on this connection before asserting.
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        enabled = int(conn.exec_driver_sql("PRAGMA foreign_keys").scalar() or 0)
    if enabled != 1:
        raise RuntimeError("SQLite foreign key enforcement is disabled (PRAGMA foreign_keys != 1).")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
