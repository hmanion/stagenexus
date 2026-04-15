from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.db.base import Base
from app.db.schema_updates import assert_runtime_integrity, ensure_runtime_schema
from app.db.session import assert_sqlite_foreign_keys_enabled, engine
from app.ui.routes import router as ui_router

# Ensure model metadata is loaded.
from app import models  # noqa: F401


app = FastAPI(title="Today Digital Campaign Operations")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    assert_sqlite_foreign_keys_enabled(engine)
    assert_runtime_integrity(engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
app.include_router(ui_router)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
