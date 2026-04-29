from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

TModel = TypeVar("TModel")


def resolve_by_identifier(db: Session, model: type[TModel], identifier: str) -> TModel | None:
    # Compatibility: allow both internal UUID and display ID during transition.
    by_pk = db.get(model, identifier)
    if by_pk:
        return by_pk
    return db.scalar(select(model).where(model.display_id == identifier))
