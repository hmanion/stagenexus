from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest


@pytest.fixture
def controlled_holidays(monkeypatch):
    holidays = (
        date(2026, 1, 1),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 4),
    )
    monkeypatch.setattr("app.services.calendar_service.holiday_snapshot", lambda: holidays)
    return set(holidays)


@pytest.fixture
def freeze_utcnow():
    active = []

    def _freeze(target: str, frozen: datetime):
        p = patch(target)
        mocked = p.start()
        mocked.utcnow.return_value = frozen
        mocked.now.return_value = frozen
        active.append(p)
        return mocked

    yield _freeze

    for p in reversed(active):
        p.stop()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
