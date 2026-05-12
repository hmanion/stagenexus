from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.domain import (
    ActivityLog,
    AppAccessRole,
    Client,
    ClientContact,
    Scope,
    ScopeStatus,
    RoleName,
    SeniorityLevel,
    TeamName,
    User,
)
from app.schemas.campaigns import CampaignOut
from app.schemas.scopes import (
    ScopeCreateIn,
    ScopeOut,
    OpsApproveIn,
    ScopeAmUpdateIn,
    ScopeContentUpdateIn,
    ScopeDeleteIn,
    ScopeTimeframeUpdateIn,
)
from app.services.authz_service import AuthzService
from app.services.campaign_generation_service import CampaignGenerationService
from app.services.scope_service import ScopeService
from app.services.id_service import PublicIdService
from app.services.calendar_service import build_default_working_calendar

from app.api.core_routes import _delete_scope_graph
from app.api.deps import get_actor, get_scope_or_404, require_scope_owner_or_roles
from app.api.permissions import can_actor_approve_scope, can_actor_generate_campaigns
from app.api.response_builders import build_scope_out, build_scope_timeframe_response

router = APIRouter(prefix="/api", tags=["campaign-ops"])


@router.post("/scopes", response_model=ScopeOut)
@router.post("/scopes", response_model=ScopeOut)
def create_scope(payload: ScopeCreateIn, actor_user_id: str, db: Session = Depends(get_db)) -> ScopeOut:
    actor = get_actor(db, actor_user_id)
    authz = AuthzService(db)
    authz.require_any(actor, {RoleName.AM, RoleName.ADMIN})
    if payload.am_user_id != actor_user_id and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor must match am_user_id unless admin")

    try:
        scope = ScopeService(db).create_scope(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return build_scope_out(db, scope)


@router.post("/scopes/{scope_id}/submit", response_model=ScopeOut)
@router.post("/scopes/{scope_id}/submit", response_model=ScopeOut)
def submit_scope(scope_id: str, actor_user_id: str, db: Session = Depends(get_db)) -> ScopeOut:
    scope = get_scope_or_404(db, scope_id)
    require_scope_owner_or_roles(db, actor_user_id, scope, {RoleName.ADMIN, RoleName.HEAD_OPS})

    ScopeService(db).submit_scope(scope)
    db.commit()
    return build_scope_out(db, scope)


@router.patch("/scopes/{scope_id}/am")
@router.patch("/scopes/{scope_id}/am")
def update_scope_am(scope_id: str, payload: ScopeAmUpdateIn, db: Session = Depends(get_db)):
    scope = get_scope_or_404(db, scope_id)
    authz = AuthzService(db)
    actor, effective_actor_user_id = authz.resolve_actor_identity(
        actor_user_id=None,
        claimed_user_id=payload.actor_user_id,
    )
    if not authz.can_update_scope(actor, scope, {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES}):
        raise HTTPException(status_code=403, detail="actor cannot modify this scope")

    next_am = db.get(User, payload.am_user_id)
    if not next_am:
        raise HTTPException(status_code=400, detail="am user not found")
    if next_am.primary_team != TeamName.SALES:
        raise HTTPException(status_code=400, detail="am user must be in sales team")

    old_am_user_id = scope.am_user_id
    if old_am_user_id == payload.am_user_id:
        return {"scope_id": scope.display_id, "am_user_id": scope.am_user_id}

    scope.am_user_id = payload.am_user_id
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=effective_actor_user_id,
            entity_type="scope",
            entity_id=scope.id,
            action="scope_am_updated",
            meta_json={
                "scope_id": scope.display_id,
                "old_am_user_id": old_am_user_id,
                "new_am_user_id": payload.am_user_id,
            },
        )
    )
    db.commit()
    return {"scope_id": scope.display_id, "am_user_id": scope.am_user_id}


@router.patch("/scopes/{scope_id}/content")
@router.patch("/scopes/{scope_id}/content")
def update_scope_content(scope_id: str, payload: ScopeContentUpdateIn, db: Session = Depends(get_db)):
    scope = get_scope_or_404(db, scope_id)
    authz = AuthzService(db)
    actor, effective_actor_user_id = authz.resolve_actor_identity(
        actor_user_id=None,
        claimed_user_id=payload.actor_user_id,
    )
    if not authz.can_update_scope(actor, scope, {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES}):
        raise HTTPException(status_code=403, detail="actor cannot modify this scope")

    client = db.get(Client, scope.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client not found for scope")
    primary_contact = db.scalars(
        select(ClientContact)
        .where(ClientContact.client_id == scope.client_id)
        .order_by(ClientContact.created_at.asc())
    ).first()

    old_client_name = client.name
    old_client_contact_name = primary_contact.name if primary_contact else None
    old_client_contact_email = primary_contact.email if primary_contact else None
    old_icp = scope.icp
    old_campaign_objective = scope.campaign_objective
    old_messaging_positioning = scope.messaging_positioning

    if payload.client_name is not None:
        next_client_name = str(payload.client_name).strip()
        if not next_client_name:
            raise HTTPException(status_code=400, detail="client name is required")
        client.name = next_client_name

    contact_name_input = payload.client_contact_name
    contact_email_input = payload.client_contact_email
    if contact_name_input is not None or contact_email_input is not None:
        next_contact_name = (
            str(contact_name_input).strip()
            if contact_name_input is not None
            else (primary_contact.name if primary_contact else "")
        )
        next_contact_email = (
            str(contact_email_input).strip()
            if contact_email_input is not None
            else (primary_contact.email if primary_contact else "")
        )
        if not next_contact_name or not next_contact_email:
            raise HTTPException(status_code=400, detail="contact name and email are required")
        if "@" not in next_contact_email:
            raise HTTPException(status_code=400, detail="contact email must be valid")
        if primary_contact:
            primary_contact.name = next_contact_name
            primary_contact.email = next_contact_email
        else:
            primary_contact = ClientContact(
                client_id=scope.client_id,
                name=next_contact_name,
                email=next_contact_email,
            )
            db.add(primary_contact)

    scope.icp = payload.icp
    scope.campaign_objective = payload.campaign_objective
    scope.messaging_positioning = payload.messaging_positioning

    if (
        old_client_name == client.name
        and old_client_contact_name == (primary_contact.name if primary_contact else None)
        and old_client_contact_email == (primary_contact.email if primary_contact else None)
        and old_icp == scope.icp
        and old_campaign_objective == scope.campaign_objective
        and old_messaging_positioning == scope.messaging_positioning
    ):
        return {
            "scope_id": scope.display_id,
            "client_name": client.name,
            "client_contact_name": primary_contact.name if primary_contact else None,
            "client_contact_email": primary_contact.email if primary_contact else None,
            "icp": scope.icp,
            "campaign_objective": scope.campaign_objective,
            "messaging_positioning": scope.messaging_positioning,
        }

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=effective_actor_user_id,
            entity_type="scope",
            entity_id=scope.id,
            action="scope_content_updated",
            meta_json={
                "scope_id": scope.display_id,
                "old_client_name": old_client_name,
                "new_client_name": client.name,
                "old_client_contact_name": old_client_contact_name,
                "new_client_contact_name": primary_contact.name if primary_contact else None,
                "old_client_contact_email": old_client_contact_email,
                "new_client_contact_email": primary_contact.email if primary_contact else None,
                "old_icp": old_icp,
                "new_icp": scope.icp,
                "old_campaign_objective": old_campaign_objective,
                "new_campaign_objective": scope.campaign_objective,
                "old_messaging_positioning": old_messaging_positioning,
                "new_messaging_positioning": scope.messaging_positioning,
            },
        )
    )
    db.commit()
    return {
        "scope_id": scope.display_id,
        "client_name": client.name,
        "client_contact_name": primary_contact.name if primary_contact else None,
        "client_contact_email": primary_contact.email if primary_contact else None,
        "icp": scope.icp,
        "campaign_objective": scope.campaign_objective,
        "messaging_positioning": scope.messaging_positioning,
    }


@router.patch("/scopes/{scope_id}/timeframe")
@router.patch("/scopes/{scope_id}/timeframe")
def update_scope_timeframe(scope_id: str, payload: ScopeTimeframeUpdateIn, db: Session = Depends(get_db)):
    scope = get_scope_or_404(db, scope_id)
    authz = AuthzService(db)
    actor, effective_actor_user_id = authz.resolve_actor_identity(
        actor_user_id=None,
        claimed_user_id=payload.actor_user_id,
    )
    authz.require_control_permission(
        actor,
        "manage_scope_timeframe",
        fallback_allowed_roles={RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES},
        detail="insufficient permissions to update scope timeframe",
    )
    if payload.sow_start_date is None and payload.sow_end_date is None:
        raise HTTPException(status_code=400, detail="at least one date is required")

    calendar = build_default_working_calendar()
    old_start = scope.sow_start_date
    old_end = scope.sow_end_date
    if payload.sow_start_date is not None:
        scope.sow_start_date = calendar.next_working_day_on_or_after(payload.sow_start_date)
    if payload.sow_end_date is not None:
        scope.sow_end_date = calendar.next_working_day_on_or_after(payload.sow_end_date)
    if scope.sow_start_date and scope.sow_end_date and scope.sow_end_date < scope.sow_start_date:
        scope.sow_end_date = scope.sow_start_date

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=effective_actor_user_id,
            entity_type="scope",
            entity_id=scope.id,
            action="scope_timeframe_updated",
            meta_json={
                "scope_id": scope.display_id,
                "old_sow_start_date": old_start.isoformat() if old_start else None,
                "old_sow_end_date": old_end.isoformat() if old_end else None,
                "new_sow_start_date": scope.sow_start_date.isoformat() if scope.sow_start_date else None,
                "new_sow_end_date": scope.sow_end_date.isoformat() if scope.sow_end_date else None,
            },
        )
    )
    db.commit()
    return build_scope_timeframe_response(scope)


@router.delete("/scopes/{scope_id}")
@router.delete("/scopes/{scope_id}")
def delete_scope(scope_id: str, payload: ScopeDeleteIn, db: Session = Depends(get_db)):
    scope = get_scope_or_404(db, scope_id)
    authz = AuthzService(db)
    actor, effective_actor_user_id = authz.resolve_actor_identity(
        actor_user_id=None,
        claimed_user_id=payload.actor_user_id,
    )
    if not authz.can_update_scope(actor, scope, {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES}):
        raise HTTPException(status_code=403, detail="actor cannot modify this scope")
    if actor.app_role != AppAccessRole.SUPERADMIN and actor.seniority not in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
        raise HTTPException(status_code=403, detail="only managers or leadership can delete scopes")

    required_phrase = f"DELETE {scope.display_id}"
    if str(payload.confirmation_phrase or "").strip() != required_phrase:
        raise HTTPException(status_code=400, detail=f"confirmation_phrase must exactly match '{required_phrase}'")

    deleted = _delete_scope_graph(db, scope.id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=effective_actor_user_id,
            entity_type="scope",
            entity_id=scope.id,
            action="scope_deleted",
            meta_json={"scope_id": scope.display_id, "deleted_counts": deleted},
        )
    )
    db.commit()
    return {"deleted": True, "scope_id": scope.display_id, "counts": deleted}


@router.post("/scopes/{scope_id}/ops-approve", response_model=ScopeOut)
@router.post("/scopes/{scope_id}/ops-approve", response_model=ScopeOut)
def ops_approve_scope(scope_id: str, payload: OpsApproveIn, actor_user_id: str, db: Session = Depends(get_db)) -> ScopeOut:
    scope = get_scope_or_404(db, scope_id)

    authz = AuthzService(db)
    actor = get_actor(db, actor_user_id)
    if not can_actor_approve_scope(db, actor):
        raise HTTPException(status_code=403, detail="insufficient permissions to approve scope")

    if not payload.head_ops_user_id:
        payload.head_ops_user_id = actor_user_id
    scope = ScopeService(db).ops_approve(scope, payload)
    db.commit()
    return build_scope_out(db, scope)


@router.post("/scopes/{scope_id}/generate-campaigns", response_model=list[CampaignOut])
@router.post("/scopes/{scope_id}/generate-campaigns", response_model=list[CampaignOut])
def generate_campaigns(scope_id: str, actor_user_id: str, db: Session = Depends(get_db)) -> list[CampaignOut]:
    scope = get_scope_or_404(db, scope_id)
    if scope.status != ScopeStatus.READINESS_PASSED:
        raise HTTPException(status_code=400, detail="scope must pass operational readiness gate")

    authz = AuthzService(db)
    actor = get_actor(db, actor_user_id)
    if not can_actor_generate_campaigns(db, actor):
        raise HTTPException(status_code=403, detail="insufficient permissions to generate campaigns")

    try:
        generated = CampaignGenerationService(db).generate_for_scope(scope)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="campaign generation failed due to data integrity constraints") from exc
    scope.status = ScopeStatus.CAMPAIGNS_GENERATED
    db.commit()

    return [
        CampaignOut(
            id=c.display_id,
            type=c.campaign_type.value,
            tier=c.tier,
            title=c.title,
        )
        for c in generated
    ]
