from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.core_routes import mark_ready_to_publish
from app.api.routes.campaigns import deliverable_history
from app.models.domain import ActivityLog, Deliverable, DeliverableStatus, DeliverableType, Publication, PublicationName


def test_ready_to_publish_transition_captures_actor_user() -> None:
    db = Mock()
    deliverable = SimpleNamespace(
        id="deliverable-1",
        display_id="DEL-001",
        status=DeliverableStatus.APPROVED,
        ready_to_publish_by_user_id=None,
        ready_to_publish_at=None,
    )
    campaign = SimpleNamespace(id="campaign-1")

    authz = Mock()
    authz.actor.return_value = SimpleNamespace(roles={"cm"})

    with patch("app.api.core_routes._resolve_by_identifier", return_value=deliverable), patch(
        "app.api.core_routes._campaign_for_deliverable", return_value=campaign
    ), patch("app.api.core_routes.AuthzService", return_value=authz):
        response = mark_ready_to_publish("DEL-001", actor_user_id="cm-1", db=db)

    assert response["status"] == "ready_to_publish"
    assert response["ready_to_publish_by_user_id"] == "cm-1"


def test_ready_to_publish_rejects_invalid_actor_role() -> None:
    db = Mock()
    deliverable = SimpleNamespace(
        id="deliverable-1",
        display_id="DEL-001",
        status=DeliverableStatus.APPROVED,
        ready_to_publish_by_user_id=None,
        ready_to_publish_at=None,
    )
    campaign = SimpleNamespace(id="campaign-1")

    authz = Mock()
    authz.actor.return_value = SimpleNamespace(roles={"am"})
    authz.require_campaign_member_or_roles.side_effect = HTTPException(status_code=403, detail="insufficient")

    with patch("app.api.core_routes._resolve_by_identifier", return_value=deliverable), patch(
        "app.api.core_routes._campaign_for_deliverable", return_value=campaign
    ), patch("app.api.core_routes.AuthzService", return_value=authz):
        with pytest.raises(HTTPException) as exc:
            mark_ready_to_publish("DEL-001", actor_user_id="am-1", db=db)
    assert exc.value.status_code == 403


def test_deliverable_history_returns_transition_history(db_session) -> None:
    publication = Publication(name=PublicationName.UC_TODAY)
    db_session.add(publication)
    db_session.flush()

    deliverable = Deliverable(
        display_id="DEL-2026-0001",
        campaign_id=None,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.READY_TO_PUBLISH,
        title="Article 1",
    )
    db_session.add(deliverable)
    db_session.flush()

    db_session.add(
        ActivityLog(
            display_id="ACT-2026-0001",
            actor_user_id="u-1",
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="status:approved->ready_to_publish",
            meta_json={"comment": ""},
        )
    )
    db_session.commit()

    payload = deliverable_history(deliverable.display_id, db_session)

    assert payload["deliverable"]["delivery_status"] == "ready_to_publish"
    assert any(item["action"] == "status:approved->ready_to_publish" for item in payload["activity"])
