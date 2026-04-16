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
    Deal,
    DealStatus,
    RoleName,
    SeniorityLevel,
    TeamName,
    User,
)
from app.schemas.campaigns import CampaignOut
from app.schemas.deals import (
    DealCreateIn,
    DealOut,
    OpsApproveIn,
    ScopeAmUpdateIn,
    ScopeContentUpdateIn,
    ScopeDeleteIn,
    ScopeTimeframeUpdateIn,
)
from app.services.authz_service import AuthzService
from app.services.campaign_generation_service import CampaignGenerationService
from app.services.deal_service import DealService
from app.services.id_service import PublicIdService
from app.services.calendar_service import build_default_working_calendar

from app.api.core_routes import _delete_scope_graph
from app.api.deps import get_actor, get_deal_or_404, require_deal_owner_or_roles
from app.api.permissions import can_actor_approve_scope, can_actor_generate_campaigns
from app.api.response_builders import build_deal_out, build_scope_timeframe_response

router = APIRouter(prefix="/api", tags=["campaign-ops"])


@router.post("/deals", response_model=DealOut)
@router.post("/scopes", response_model=DealOut)
def create_deal(payload: DealCreateIn, actor_user_id: str, db: Session = Depends(get_db)) -> DealOut:
    actor = get_actor(db, actor_user_id)
    authz = AuthzService(db)
    authz.require_any(actor, {RoleName.AM, RoleName.ADMIN})
    if payload.am_user_id != actor_user_id and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor must match am_user_id unless admin")

    try:
        deal = DealService(db).create_deal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return build_deal_out(db, deal)


@router.post("/deals/{deal_id}/submit", response_model=DealOut)
@router.post("/scopes/{deal_id}/submit", response_model=DealOut)
def submit_deal(deal_id: str, actor_user_id: str, db: Session = Depends(get_db)) -> DealOut:
    deal = get_deal_or_404(db, deal_id)
    require_deal_owner_or_roles(db, actor_user_id, deal, {RoleName.ADMIN, RoleName.HEAD_OPS})

    DealService(db).submit_deal(deal)
    db.commit()
    return build_deal_out(db, deal)


@router.patch("/deals/{deal_id}/am")
@router.patch("/scopes/{deal_id}/am")
def update_scope_am(deal_id: str, payload: ScopeAmUpdateIn, db: Session = Depends(get_db)):
    deal = get_deal_or_404(db, deal_id)
    require_deal_owner_or_roles(
        db,
        payload.actor_user_id,
        deal,
        {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES},
    )

    next_am = db.get(User, payload.am_user_id)
    if not next_am:
        raise HTTPException(status_code=400, detail="am user not found")
    if next_am.primary_team != TeamName.SALES:
        raise HTTPException(status_code=400, detail="am user must be in sales team")

    old_am_user_id = deal.am_user_id
    if old_am_user_id == payload.am_user_id:
        return {"scope_id": deal.display_id, "am_user_id": deal.am_user_id}

    deal.am_user_id = payload.am_user_id
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="scope",
            entity_id=deal.id,
            action="scope_am_updated",
            meta_json={
                "scope_id": deal.display_id,
                "old_am_user_id": old_am_user_id,
                "new_am_user_id": payload.am_user_id,
            },
        )
    )
    db.commit()
    return {"scope_id": deal.display_id, "am_user_id": deal.am_user_id}


@router.patch("/deals/{deal_id}/content")
@router.patch("/scopes/{deal_id}/content")
def update_scope_content(deal_id: str, payload: ScopeContentUpdateIn, db: Session = Depends(get_db)):
    deal = get_deal_or_404(db, deal_id)
    require_deal_owner_or_roles(
        db,
        payload.actor_user_id,
        deal,
        {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES},
    )

    client = db.get(Client, deal.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client not found for scope")
    primary_contact = db.scalars(
        select(ClientContact)
        .where(ClientContact.client_id == deal.client_id)
        .order_by(ClientContact.created_at.asc())
    ).first()

    old_client_name = client.name
    old_client_contact_name = primary_contact.name if primary_contact else None
    old_client_contact_email = primary_contact.email if primary_contact else None
    old_icp = deal.icp
    old_campaign_objective = deal.campaign_objective
    old_messaging_positioning = deal.messaging_positioning

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
                client_id=deal.client_id,
                name=next_contact_name,
                email=next_contact_email,
            )
            db.add(primary_contact)

    deal.icp = payload.icp
    deal.campaign_objective = payload.campaign_objective
    deal.messaging_positioning = payload.messaging_positioning

    if (
        old_client_name == client.name
        and old_client_contact_name == (primary_contact.name if primary_contact else None)
        and old_client_contact_email == (primary_contact.email if primary_contact else None)
        and old_icp == deal.icp
        and old_campaign_objective == deal.campaign_objective
        and old_messaging_positioning == deal.messaging_positioning
    ):
        return {
            "scope_id": deal.display_id,
            "client_name": client.name,
            "client_contact_name": primary_contact.name if primary_contact else None,
            "client_contact_email": primary_contact.email if primary_contact else None,
            "icp": deal.icp,
            "campaign_objective": deal.campaign_objective,
            "messaging_positioning": deal.messaging_positioning,
        }

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="scope",
            entity_id=deal.id,
            action="scope_content_updated",
            meta_json={
                "scope_id": deal.display_id,
                "old_client_name": old_client_name,
                "new_client_name": client.name,
                "old_client_contact_name": old_client_contact_name,
                "new_client_contact_name": primary_contact.name if primary_contact else None,
                "old_client_contact_email": old_client_contact_email,
                "new_client_contact_email": primary_contact.email if primary_contact else None,
                "old_icp": old_icp,
                "new_icp": deal.icp,
                "old_campaign_objective": old_campaign_objective,
                "new_campaign_objective": deal.campaign_objective,
                "old_messaging_positioning": old_messaging_positioning,
                "new_messaging_positioning": deal.messaging_positioning,
            },
        )
    )
    db.commit()
    return {
        "scope_id": deal.display_id,
        "client_name": client.name,
        "client_contact_name": primary_contact.name if primary_contact else None,
        "client_contact_email": primary_contact.email if primary_contact else None,
        "icp": deal.icp,
        "campaign_objective": deal.campaign_objective,
        "messaging_positioning": deal.messaging_positioning,
    }


@router.patch("/deals/{deal_id}/timeframe")
@router.patch("/scopes/{deal_id}/timeframe")
def update_scope_timeframe(deal_id: str, payload: ScopeTimeframeUpdateIn, db: Session = Depends(get_db)):
    deal = get_deal_or_404(db, deal_id)
    actor = require_deal_owner_or_roles(
        db,
        payload.actor_user_id,
        deal,
        {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES},
    )
    if actor.app_role != AppAccessRole.SUPERADMIN and actor.seniority not in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
        raise HTTPException(status_code=403, detail="only managers or leadership can update scope timeframe")
    if payload.sow_start_date is None and payload.sow_end_date is None:
        raise HTTPException(status_code=400, detail="at least one date is required")

    calendar = build_default_working_calendar()
    old_start = deal.sow_start_date
    old_end = deal.sow_end_date
    if payload.sow_start_date is not None:
        deal.sow_start_date = calendar.next_working_day_on_or_after(payload.sow_start_date)
    if payload.sow_end_date is not None:
        deal.sow_end_date = calendar.next_working_day_on_or_after(payload.sow_end_date)
    if deal.sow_start_date and deal.sow_end_date and deal.sow_end_date < deal.sow_start_date:
        deal.sow_end_date = deal.sow_start_date

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="scope",
            entity_id=deal.id,
            action="scope_timeframe_updated",
            meta_json={
                "scope_id": deal.display_id,
                "old_sow_start_date": old_start.isoformat() if old_start else None,
                "old_sow_end_date": old_end.isoformat() if old_end else None,
                "new_sow_start_date": deal.sow_start_date.isoformat() if deal.sow_start_date else None,
                "new_sow_end_date": deal.sow_end_date.isoformat() if deal.sow_end_date else None,
            },
        )
    )
    db.commit()
    return build_scope_timeframe_response(deal)


@router.delete("/deals/{deal_id}")
@router.delete("/scopes/{deal_id}")
def delete_scope(deal_id: str, payload: ScopeDeleteIn, db: Session = Depends(get_db)):
    deal = get_deal_or_404(db, deal_id)
    actor = require_deal_owner_or_roles(
        db,
        payload.actor_user_id,
        deal,
        {RoleName.ADMIN, RoleName.HEAD_OPS, RoleName.HEAD_SALES},
    )
    if actor.app_role != AppAccessRole.SUPERADMIN and actor.seniority not in {SeniorityLevel.MANAGER, SeniorityLevel.LEADERSHIP}:
        raise HTTPException(status_code=403, detail="only managers or leadership can delete scopes")

    required_phrase = f"DELETE {deal.display_id}"
    if str(payload.confirmation_phrase or "").strip() != required_phrase:
        raise HTTPException(status_code=400, detail=f"confirmation_phrase must exactly match '{required_phrase}'")

    deleted = _delete_scope_graph(db, deal.id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="scope",
            entity_id=deal.id,
            action="scope_deleted",
            meta_json={"scope_id": deal.display_id, "deleted_counts": deleted},
        )
    )
    db.commit()
    return {"deleted": True, "scope_id": deal.display_id, "counts": deleted}


@router.post("/deals/{deal_id}/ops-approve", response_model=DealOut)
@router.post("/scopes/{deal_id}/ops-approve", response_model=DealOut)
def ops_approve_deal(deal_id: str, payload: OpsApproveIn, actor_user_id: str, db: Session = Depends(get_db)) -> DealOut:
    deal = get_deal_or_404(db, deal_id)

    authz = AuthzService(db)
    actor = get_actor(db, actor_user_id)
    if not can_actor_approve_scope(db, actor):
        raise HTTPException(status_code=403, detail="insufficient permissions to approve scope")

    if not payload.head_ops_user_id:
        payload.head_ops_user_id = actor_user_id
    deal = DealService(db).ops_approve(deal, payload)
    db.commit()
    return build_deal_out(db, deal)


@router.post("/deals/{deal_id}/generate-campaigns", response_model=list[CampaignOut])
@router.post("/scopes/{deal_id}/generate-campaigns", response_model=list[CampaignOut])
def generate_campaigns(deal_id: str, actor_user_id: str, db: Session = Depends(get_db)) -> list[CampaignOut]:
    deal = get_deal_or_404(db, deal_id)
    if deal.status != DealStatus.READINESS_PASSED:
        raise HTTPException(status_code=400, detail="scope must pass operational readiness gate")

    authz = AuthzService(db)
    actor = get_actor(db, actor_user_id)
    if not can_actor_generate_campaigns(db, actor):
        raise HTTPException(status_code=403, detail="insufficient permissions to generate campaigns")

    try:
        generated = CampaignGenerationService(db).generate_for_deal(deal)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="campaign generation failed due to data integrity constraints") from exc
    deal.status = DealStatus.CAMPAIGNS_GENERATED
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

