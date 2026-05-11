from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.core.config import settings
from app.db.base import Base
from app.db.migration_guard import assert_database_at_migration_head
from app.db.schema_updates import assert_runtime_integrity, ensure_runtime_schema
from app.db.session import SessionLocal, assert_sqlite_foreign_keys_enabled, engine
from app.seeds.reference_data import get_stage_steps_from_db
from app.ui.routes import router as ui_router

# Ensure model metadata is loaded.
from app import models  # noqa: F401


app = FastAPI(title="Today Digital Campaign Operations")


@app.on_event("startup")
def startup() -> None:
    settings.validate_for_environment()

    if settings.runtime_schema_compat:
        # Local/dev compatibility path for pre-Alembic databases. Staging and
        # production should run Alembic migrations before startup instead.
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)
    elif not settings.is_local_env:
        assert_database_at_migration_head(engine)
    assert_sqlite_foreign_keys_enabled(engine)
    assert_runtime_integrity(engine)
    if not settings.is_local_env:
        with SessionLocal() as session:
            has_db_reference = bool(get_stage_steps_from_db(session))
        has_csv_fallback = settings.stage_steps_csv_path_resolved.exists()
        if not has_db_reference and not has_csv_fallback:
            raise RuntimeError(
                "Stage/step reference data is missing. Seed DB reference data with "
                "`PYTHONPATH=. python scripts/seed_reference_data.py` or configure "
                "STAGE_STEPS_CSV_PATH to a valid CSV."
            )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
app.include_router(ui_router)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
