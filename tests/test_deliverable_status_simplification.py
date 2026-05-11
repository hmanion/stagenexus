from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.api.core_routes import _compute_deliverable_display_status, mark_ready_to_publish
from app.api.routes.campaigns import deliverable_history
from app.models.domain import Deliverable, DeliverableStatus, DeliverableType, Publication, PublicationName, RoleName, WorkflowStep, WorkflowStepKind
from app.services.my_work_queue_service import MyWorkQueueService


def test_display_status_uses_current_open_step_name_without_relying_on_deliverable_status(db_session) -> None:
    publication = Publication(name=PublicationName.UC_TODAY)
    db_session.add(publication)
    db_session.flush()

    deliverable = Deliverable(
        display_id="DEL-2026-1001",
        campaign_id=None,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.COMPLETE,
        title="Article status derivation",
    )
    db_session.add(deliverable)
    db_session.flush()

    db_session.add(
        WorkflowStep(
            display_id="STEP-2026-1001",
            campaign_id=None,
            stage_id="stage-1",
            name="Draft",
            step_kind=WorkflowStepKind.TASK,
            owner_role=RoleName.CM,
            linked_deliverable_id=deliverable.id,
            actual_start=datetime.utcnow(),
            actual_done=datetime.utcnow(),
        )
    )
    db_session.add(
        WorkflowStep(
            display_id="STEP-2026-1002",
            campaign_id=None,
            stage_id="stage-1",
            name="Review",
            step_kind=WorkflowStepKind.TASK,
            owner_role=RoleName.CM,
            linked_deliverable_id=deliverable.id,
            actual_start=datetime.utcnow(),
            actual_done=None,
        )
    )
    db_session.commit()

    assert _compute_deliverable_display_status(db_session, deliverable) == "review"


def test_mark_ready_to_publish_sets_readiness_fields_without_writing_workflow_state() -> None:
    db = Mock()
    deliverable = SimpleNamespace(
        id="deliverable-1",
        display_id="DEL-001",
        status=DeliverableStatus.APPROVED,
        ready_to_publish_by_user_id=None,
        ready_to_publish_by_role=None,
        ready_to_publish_at=None,
    )
    campaign = SimpleNamespace(id="campaign-1")

    authz = Mock()
    authz.actor.return_value = SimpleNamespace(roles={RoleName.CM})

    with patch("app.api.core_routes._resolve_by_identifier", return_value=deliverable), patch(
        "app.api.core_routes._campaign_for_deliverable", return_value=campaign
    ), patch("app.api.core_routes.AuthzService", return_value=authz):
        response = mark_ready_to_publish("DEL-001", actor_user_id="cm-1", db=db)

    assert response["ready_to_publish_by_user_id"] == "cm-1"
    assert response["ready_to_publish_by_role"] == "cm"
    assert response["display_status"] == "ready_to_publish"
    assert not hasattr(deliverable, "workflow_state")


def test_published_deliverable_displays_published_even_without_current_step(db_session) -> None:
    publication = Publication(name=PublicationName.UC_TODAY)
    db_session.add(publication)
    db_session.flush()

    deliverable = Deliverable(
        display_id="DEL-2026-1003",
        campaign_id=None,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.IN_PROGRESS,
        title="Published fallback",
        scheduled_or_published_at=datetime.utcnow(),
    )
    db_session.add(deliverable)
    db_session.commit()

    assert _compute_deliverable_display_status(db_session, deliverable) == "published"


def test_cancelled_deliverable_is_not_selected_as_active_work(db_session) -> None:
    publication = Publication(name=PublicationName.UC_TODAY)
    db_session.add(publication)
    db_session.flush()

    deliverable = Deliverable(
        display_id="DEL-2026-1004",
        campaign_id=None,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.IN_PROGRESS,
        title="Cancelled work item",
    )
    setattr(deliverable, "cancelled_at", datetime.utcnow())
    db_session.add(deliverable)
    db_session.flush()

    db_session.add(
        WorkflowStep(
            display_id="STEP-2026-1004",
            campaign_id=None,
            stage_id="stage-1",
            name="Review",
            step_kind=WorkflowStepKind.TASK,
            owner_role=RoleName.CM,
            linked_deliverable_id=deliverable.id,
            next_owner_user_id="u-1",
            actual_done=None,
        )
    )
    db_session.commit()

    payload = MyWorkQueueService(db_session).build("u-1")
    assert payload["summary"]["total"] == 0


def test_deliverable_history_status_and_current_step_are_not_contradictory(db_session) -> None:
    publication = Publication(name=PublicationName.UC_TODAY)
    db_session.add(publication)
    db_session.flush()

    deliverable = Deliverable(
        display_id="DEL-2026-1005",
        campaign_id=None,
        publication_id=publication.id,
        deliverable_type=DeliverableType.ARTICLE,
        status=DeliverableStatus.COMPLETE,
        title="History consistency",
        scheduled_or_published_at=datetime.utcnow(),
    )
    db_session.add(deliverable)
    db_session.commit()

    payload = deliverable_history(deliverable.display_id, db_session)

    assert payload["deliverable"]["status"] == "done"
    assert payload["deliverable"]["display_status"] == "published"
    assert payload["deliverable"]["current_step_id"] is None
