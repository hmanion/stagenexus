from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.domain import (
    ActivityLog,
    Campaign,
    CampaignAssignment,
    Client,
    ClientContact,
    Deal,
    DealAttachment,
    DealProductLine,
    Deliverable,
    GlobalStatus,
    Milestone,
    Publication,
    RoleName,
    SeniorityLevel,
    Stage,
    User,
    UserRoleAssignment,
    WorkflowStep,
    WorkflowStepEffort,
)
from app.schemas.campaigns import CampaignOut, CampaignStatusUpdateIn
from app.schemas.deals import OpsApproveIn, ScopeDeleteIn
from app.schemas.milestones import MilestoneUpdateIn
from app.services.authz_service import AuthzService
from app.services.campaign_health_service import CampaignHealthService
from app.services.id_service import PublicIdService
from app.services.team_inference_service import TeamInferenceService
from app.services.timeline_health_service import TimelineHealthService

from app.api.core_routes import (
    _actor_has_control_permission,
    _actor_has_full_scope_campaign_visibility,
    _campaign_timeframe_from_milestones,
    _delete_campaign_graph,
    _deliverable_stage_from_record,
    _derived_deliverable_status,
    _initials_for_user_id,
    _normalize_campaign_status,
    _normalize_deliverable_status,
    _normalize_step_status,
    _participant_initials_for_step,
    _resolve_by_identifier,
    _step_linked_deliverable,
)

router = APIRouter(prefix="/api", tags=["campaign-ops"])


@router.get("/campaigns/health")
def list_campaigns_health(
    owner: str | None = None,
    status: str | None = None,
    publication: str | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    payload = CampaignHealthService(db).evaluate_many(
        campaigns=campaigns,
        owner=owner,
        status=status,
        publication=publication,
        limit=limit,
        offset=offset,
    )
    return payload


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    return {
        "id": campaign.display_id,
        "title": campaign.title,
        "type": campaign.campaign_type.value,
        "tier": campaign.tier,
        "template_version_id": campaign.template_version_id,
    }


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, actor_user_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    allowed = _actor_has_control_permission(
        db,
        actor,
        "delete_campaign",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="not permitted to delete campaign")

    deleted = _delete_campaign_graph(db, campaign.id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_deleted",
            meta_json={"campaign_id": campaign.display_id, "deleted_counts": deleted},
        )
    )
    db.commit()
    return {"deleted": True, "campaign_id": campaign.display_id, "counts": deleted}


@router.get("/deals")
@router.get("/scopes")
def list_deals(
    limit: int = 25,
    offset: int = 0,
    q: str | None = None,
    actor_user_id: str | None = None,
    db: Session = Depends(get_db),
):
    actor = None
    full_visibility = True
    if actor_user_id:
        actor = AuthzService(db).actor(actor_user_id)
        full_visibility = _actor_has_full_scope_campaign_visibility(actor)

    deals = db.scalars(select(Deal).order_by(Deal.created_at.desc())).all()
    campaigns = db.scalars(select(Campaign)).all()
    campaigns_by_deal: dict[str, list[Campaign]] = {}
    for c in campaigns:
        campaigns_by_deal.setdefault(c.deal_id, []).append(c)
    assignments = db.scalars(select(CampaignAssignment)).all()
    assignments_by_campaign: dict[str, list[CampaignAssignment]] = {}
    for a in assignments:
        assignments_by_campaign.setdefault(a.campaign_id, []).append(a)
    milestones = db.scalars(select(Milestone)).all()
    milestones_by_campaign: dict[str, list[Milestone]] = {}
    for m in milestones:
        milestones_by_campaign.setdefault(m.campaign_id, []).append(m)
    all_deliverables = db.scalars(select(Deliverable)).all()
    deliverables_by_campaign: dict[str, list[Deliverable]] = {}
    for d in all_deliverables:
        if d.campaign_id:
            deliverables_by_campaign.setdefault(d.campaign_id, []).append(d)
    all_steps = db.scalars(select(WorkflowStep)).all()
    steps_by_campaign: dict[str, list[WorkflowStep]] = {}
    for s in all_steps:
        if s.campaign_id:
            steps_by_campaign.setdefault(s.campaign_id, []).append(s)
        elif _step_linked_deliverable(s):
            parent = next((d for d in all_deliverables if d.id == _step_linked_deliverable(s) and d.campaign_id), None)
            if parent:
                steps_by_campaign.setdefault(parent.campaign_id, []).append(s)
    step_ids = [s.id for s in all_steps]
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if step_ids:
        for e in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts_by_step.setdefault(e.workflow_step_id, []).append(e)
    timeline_health = TimelineHealthService(db)
    team_inference = TeamInferenceService(db)
    clients = {c.id: c for c in db.scalars(select(Client)).all()}
    contacts_by_client: dict[str, list[ClientContact]] = {}
    for contact in db.scalars(select(ClientContact).order_by(ClientContact.created_at.asc())).all():
        contacts_by_client.setdefault(contact.client_id, []).append(contact)
    attachments_by_deal: dict[str, list[DealAttachment]] = {}
    for attachment in db.scalars(select(DealAttachment).order_by(DealAttachment.created_at.desc())).all():
        attachments_by_deal.setdefault(attachment.deal_id, []).append(attachment)
    product_lines = db.scalars(select(DealProductLine)).all()
    lines_by_deal: dict[str, list[DealProductLine]] = {}
    for line in product_lines:
        lines_by_deal.setdefault(line.deal_id, []).append(line)
    assignment_user_ids = {
        assignment.user_id
        for assignment_list in assignments_by_campaign.values()
        for assignment in assignment_list
        if assignment.user_id
    }
    am_user_ids = {deal.am_user_id for deal in deals if deal.am_user_id}
    staffing_user_ids = {
        user_id
        for deal in deals
        for user_id in (deal.assigned_cm_user_id, deal.assigned_cc_user_id, deal.assigned_ccs_user_id)
        if user_id
    }
    deliverable_owner_user_ids = {
        d.owner_user_id
        for rows in deliverables_by_campaign.values()
        for d in rows
        if d.owner_user_id
    }
    step_owner_user_ids = {
        s.next_owner_user_id
        for rows in steps_by_campaign.values()
        for s in rows
        if s.next_owner_user_id
    }
    user_ids = sorted(
        assignment_user_ids
        .union(am_user_ids)
        .union(staffing_user_ids)
        .union(deliverable_owner_user_ids)
        .union(step_owner_user_ids)
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    assignment_user_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in assignments_by_campaign.items():
        assignment_user_ids_by_campaign[campaign_id] = {r.user_id for r in rows if r.user_id}
    deliverable_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in deliverables_by_campaign.items():
        deliverable_owner_ids_by_campaign[campaign_id] = {d.owner_user_id for d in rows if d.owner_user_id}
    step_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in steps_by_campaign.items():
        step_owner_ids_by_campaign[campaign_id] = {s.next_owner_user_id for s in rows if s.next_owner_user_id}

    def _campaign_visible_for_actor(campaign: Campaign) -> bool:
        if full_visibility or not actor:
            return True
        campaign_user_ids = (
            assignment_user_ids_by_campaign.get(campaign.id, set())
            .union(deliverable_owner_ids_by_campaign.get(campaign.id, set()))
            .union(step_owner_ids_by_campaign.get(campaign.id, set()))
        )
        if actor.seniority == SeniorityLevel.MANAGER:
            return any(
                (uid in users_by_id) and (users_by_id[uid].primary_team == actor.primary_team)
                for uid in campaign_user_ids
            )
        return actor.user_id in campaign_user_ids

    def _deal_visible_for_actor(deal: Deal, child_campaigns: list[Campaign]) -> bool:
        if full_visibility or not actor:
            return True
        if actor.seniority == SeniorityLevel.MANAGER:
            deal_user_ids = {
                deal.am_user_id,
                deal.assigned_cm_user_id,
                deal.assigned_cc_user_id,
                deal.assigned_ccs_user_id,
            }
            deal_user_ids = {uid for uid in deal_user_ids if uid}
            team_matches_deal = any(
                (uid in users_by_id) and (users_by_id[uid].primary_team == actor.primary_team)
                for uid in deal_user_ids
            )
            return team_matches_deal or any(_campaign_visible_for_actor(c) for c in child_campaigns)
        return (
            actor.user_id == deal.am_user_id
            or actor.user_id in {deal.assigned_cm_user_id, deal.assigned_cc_user_id, deal.assigned_ccs_user_id}
            or any(_campaign_visible_for_actor(c) for c in child_campaigns)
        )
    all_items = []
    for d in deals:
        deal_campaigns = campaigns_by_deal.get(d.id, [])
        if not _deal_visible_for_actor(d, deal_campaigns):
            continue
        campaign_evals: list[tuple[Campaign, Any]] = []
        for c in deal_campaigns:
            c_eval, _ = timeline_health.evaluate_campaign(
                campaign=c,
                deliverables=deliverables_by_campaign.get(c.id, []),
                steps=steps_by_campaign.get(c.id, []),
                efforts_by_step_id=efforts_by_step,
                assignments=assignments_by_campaign.get(c.id, []),
                stages=db.scalars(select(Stage).where(Stage.campaign_id == c.id)).all(),
            )
            campaign_evals.append((c, c_eval))
        scope_campaigns = []
        for c, c_eval in sorted(
            campaign_evals,
            key=lambda row: (
                row[0].planned_start_date or date.max,
                row[0].created_at or datetime.max,
            ),
        ):
            milestone_window = _campaign_timeframe_from_milestones(milestones_by_campaign.get(c.id, []))
            scope_campaigns.append(
                {
                    "id": c.display_id,
                    "campaign_internal_id": c.id,
                    "type": c.campaign_type.value,
                    "tier": c.tier,
                    "title": c.title,
                    "scope_id": d.display_id,
                    "status": _normalize_campaign_status(c.status).value,
                    "health": str(c_eval.health or "not_started"),
                    "health_reason": c_eval.health_reason,
                    "buffer_working_days_remaining": c_eval.buffer_working_days_remaining,
                    "is_not_due": c_eval.is_not_due,
                    "is_demand_sprint": c.is_demand_sprint,
                    "demand_sprint_number": c.demand_sprint_number,
                    "demand_track": c.demand_track,
                    "sprint_label": (
                        f"S{c.demand_sprint_number}"
                        if c.is_demand_sprint and c.demand_sprint_number
                        else None
                    ),
                    "timeframe_start": c.planned_start_date.isoformat() if c.planned_start_date else milestone_window[0],
                    "timeframe_due": c.planned_end_date.isoformat() if c.planned_end_date else milestone_window[1],
                    "assigned_users": [
                        {
                            "user_id": assignment.user_id,
                            "name": users_by_id.get(assignment.user_id).full_name if users_by_id.get(assignment.user_id) else None,
                            "initials": _initials_for_user_id(assignment.user_id, users_by_id),
                            "role": assignment.role_name.value,
                        }
                        for assignment in sorted(assignments_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                    ],
                    "assigned_user_initials": [
                        _initials_for_user_id(assignment.user_id, users_by_id)
                        for assignment in sorted(assignments_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                        if assignment.user_id
                    ],
                    "deliverables_summary": {"total": 0, "not_started": 0, "in_progress": 0, "done": 0},
                    "work_summary": {"total": 0, "not_started": 0, "in_progress": 0, "done": 0},
                    "deliverables": [],
                    "work_steps": [],
                }
            )
        scope_eval = timeline_health.evaluate_scope(d, campaign_evals)
        scope_contacts = contacts_by_client.get(d.client_id, [])
        primary_contact = scope_contacts[0] if scope_contacts else None
        scope_attachments = attachments_by_deal.get(d.id, [])
        am_user = users_by_id.get(d.am_user_id)
        all_items.append({
                "id": d.display_id,
                "client_name": clients.get(d.client_id).name if clients.get(d.client_id) else None,
                "brand_publication": d.brand_publication.value,
                "status": d.status.value,
                "health": scope_eval.health,
                "health_reason": scope_eval.health_reason,
                "buffer_working_days_remaining": scope_eval.buffer_working_days_remaining,
                "is_not_due": scope_eval.is_not_due,
                "sow_start_date": d.sow_start_date.isoformat() if d.sow_start_date else None,
                "sow_end_date": d.sow_end_date.isoformat() if d.sow_end_date else None,
                "icp": d.icp,
                "campaign_objective": d.campaign_objective,
                "messaging_positioning": d.messaging_positioning,
                "commercial_notes": d.commercial_notes,
                "product_lines": [
                    {
                        "product_type": line.product_type.value,
                        "tier": line.tier,
                    }
                    for line in lines_by_deal.get(d.id, [])
                ],
                "am_user": {
                    "user_id": d.am_user_id,
                    "name": am_user.full_name if am_user else None,
                    "initials": _initials_for_user_id(d.am_user_id, users_by_id),
                },
                "assigned_cm_user_id": d.assigned_cm_user_id,
                "assigned_cc_user_id": d.assigned_cc_user_id,
                "assigned_ccs_user_id": d.assigned_ccs_user_id,
                "client_contact_name": primary_contact.name if primary_contact else None,
                "client_contact_email": primary_contact.email if primary_contact else None,
                "attachments": [
                    {
                        "file_name": attachment.file_name,
                        "storage_key": attachment.storage_key,
                    }
                    for attachment in scope_attachments
                ],
                "inferred_team_key": team_inference.infer_scope_team_key(d.id),
                "campaigns": scope_campaigns,
                "readiness_passed": d.readiness_passed,
                "created_at": d.created_at.isoformat(),
            })
    if q:
        needle = q.strip().lower()
        all_items = [
            item
            for item in all_items
            if needle in " ".join(
                [
                    item["id"] or "",
                    item["client_name"] or "",
                    item["brand_publication"] or "",
                    item["status"] or "",
                    item["campaign_objective"] or "",
                ]
            ).lower()
        ]
    total = len(all_items)
    items = all_items[offset : offset + limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/publications")
def list_publications(db: Session = Depends(get_db)):
    pubs = db.scalars(select(Publication).order_by(Publication.name.asc())).all()
    return {"items": [{"id": p.id, "name": p.name.value} for p in pubs]}


@router.get("/campaigns")
def list_campaigns(
    limit: int = 25,
    offset: int = 0,
    q: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    actor_user_id: str | None = None,
    db: Session = Depends(get_db),
):
    actor = None
    full_visibility = True
    if actor_user_id:
        actor = AuthzService(db).actor(actor_user_id)
        full_visibility = _actor_has_full_scope_campaign_visibility(actor)

    campaigns = db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()
    deals_by_id = {d.id: d for d in db.scalars(select(Deal)).all()}
    assignments = db.scalars(select(CampaignAssignment)).all()
    campaign_ids = [c.id for c in campaigns]
    deliverables_by_campaign: dict[str, list[Deliverable]] = {}
    workflow_steps_by_campaign: dict[str, list[WorkflowStep]] = {}
    step_efforts_by_step_id: dict[str, list[WorkflowStepEffort]] = {}
    if campaign_ids:
        deliverable_rows = db.scalars(select(Deliverable).where(Deliverable.campaign_id.in_(campaign_ids))).all()
        for d in deliverable_rows:
            deliverables_by_campaign.setdefault(d.campaign_id, []).append(d)
        workflow_rows = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id.in_(campaign_ids))).all()
        for s in workflow_rows:
            workflow_steps_by_campaign.setdefault(s.campaign_id, []).append(s)
        step_ids = [s.id for s in workflow_rows]
        if step_ids:
            effort_rows = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
            for e in effort_rows:
                step_efforts_by_step_id.setdefault(e.workflow_step_id, []).append(e)
    owners_by_campaign: dict[str, set[str]] = {}
    assignment_rows_by_campaign: dict[str, list[CampaignAssignment]] = {}
    for a in assignments:
        owners_by_campaign.setdefault(a.campaign_id, set()).add(a.user_id)
        assignment_rows_by_campaign.setdefault(a.campaign_id, []).append(a)

    milestones_by_campaign: dict[str, list[Milestone]] = {}
    if campaign_ids:
        milestone_rows = db.scalars(select(Milestone).where(Milestone.campaign_id.in_(campaign_ids))).all()
        for m in milestone_rows:
            milestones_by_campaign.setdefault(m.campaign_id, []).append(m)
    timeframe_by_campaign = {
        cid: _campaign_timeframe_from_milestones(rows)
        for cid, rows in milestones_by_campaign.items()
    }

    user_ids = sorted(
        {
            a.user_id
            for a in assignments
            if a.user_id
        }
        .union(
            {
                s.next_owner_user_id
                for rows in workflow_steps_by_campaign.values()
                for s in rows
                if s.next_owner_user_id
            }
        )
        .union(
            {
                e.assigned_user_id
                for rows in step_efforts_by_step_id.values()
                for e in rows
                if e.assigned_user_id
            }
        )
        .union(
            {
                d.owner_user_id
                for rows in deliverables_by_campaign.values()
                for d in rows
                if d.owner_user_id
            }
        )
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    assignment_user_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in assignment_rows_by_campaign.items():
        assignment_user_ids_by_campaign[campaign_id] = {r.user_id for r in rows if r.user_id}
    deliverable_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in deliverables_by_campaign.items():
        deliverable_owner_ids_by_campaign[campaign_id] = {d.owner_user_id for d in rows if d.owner_user_id}
    step_owner_ids_by_campaign: dict[str, set[str]] = {}
    for campaign_id, rows in workflow_steps_by_campaign.items():
        step_owner_ids_by_campaign[campaign_id] = {s.next_owner_user_id for s in rows if s.next_owner_user_id}

    def _campaign_visible_for_actor(campaign: Campaign) -> bool:
        if full_visibility or not actor:
            return True
        campaign_user_ids = (
            assignment_user_ids_by_campaign.get(campaign.id, set())
            .union(deliverable_owner_ids_by_campaign.get(campaign.id, set()))
            .union(step_owner_ids_by_campaign.get(campaign.id, set()))
        )
        if actor.seniority == SeniorityLevel.MANAGER:
            return any(
                (uid in users_by_id) and (users_by_id[uid].primary_team == actor.primary_team)
                for uid in campaign_user_ids
            )
        return actor.user_id in campaign_user_ids

    timeline_health = TimelineHealthService(db)
    health_by_campaign: dict[str, dict] = {}
    derived_stage_by_campaign: dict[str, str] = {}
    for c in campaigns:
        c_deliverables = deliverables_by_campaign.get(c.id, [])
        c_steps = workflow_steps_by_campaign.get(c.id, [])
        c_assignments = assignment_rows_by_campaign.get(c.id, [])
        eval_result, derived_stage = timeline_health.evaluate_campaign(
            campaign=c,
            deliverables=c_deliverables,
            steps=c_steps,
            efforts_by_step_id=step_efforts_by_step_id,
            assignments=c_assignments,
        )
        health_by_campaign[c.id] = {
            "overall_status": eval_result.health,
            "health_reason": eval_result.health_reason,
            "buffer_working_days_remaining": eval_result.buffer_working_days_remaining,
            "is_not_due": eval_result.is_not_due,
        }
        derived_stage_by_campaign[c.id] = derived_stage

    all_items = [
            {
                "id": c.display_id,
                "campaign_internal_id": c.id,
                "type": c.campaign_type.value,
                "tier": c.tier,
                "title": c.title,
                "scope_id": deals_by_id.get(c.deal_id).display_id if deals_by_id.get(c.deal_id) else None,
                "status": _normalize_campaign_status(c.status).value,
                "status_source": str(c.status_source.value if hasattr(c.status_source, "value") else c.status_source or "derived"),
                "status_overridden_by_user_id": c.status_overridden_by_user_id,
                "is_demand_sprint": c.is_demand_sprint,
                "demand_sprint_number": c.demand_sprint_number,
                "demand_track": c.demand_track,
                "sprint_label": (f"S{c.demand_sprint_number}" if c.is_demand_sprint and c.demand_sprint_number else None),
                "template_version_id": c.template_version_id,
                "owner_user_ids": sorted(list(owners_by_campaign.get(c.id, set()))),
                "module_type": "campaign",
                "health": str((health_by_campaign.get(c.id) or {}).get("overall_status") or "not_started"),
                "health_reason": (health_by_campaign.get(c.id) or {}).get("health_reason"),
                "buffer_working_days_remaining": (health_by_campaign.get(c.id) or {}).get("buffer_working_days_remaining"),
                "is_not_due": bool((health_by_campaign.get(c.id) or {}).get("is_not_due")),
                "timeframe_start": (c.planned_start_date.isoformat() if c.planned_start_date else (timeframe_by_campaign.get(c.id) or (None, None))[0]),
                "timeframe_due": (c.planned_end_date.isoformat() if c.planned_end_date else (timeframe_by_campaign.get(c.id) or (None, None))[1]),
                "derived_stage": derived_stage_by_campaign.get(c.id, "not_started"),
                "assigned_users": [
                    {
                        "user_id": a.user_id,
                        "name": users_by_id.get(a.user_id).full_name if users_by_id.get(a.user_id) else None,
                        "initials": _initials_for_user_id(a.user_id, users_by_id),
                        "role": a.role_name.value,
                    }
                    for a in sorted(assignment_rows_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                ],
                "assigned_user_initials": [
                    _initials_for_user_id(a.user_id, users_by_id)
                    for a in sorted(assignment_rows_by_campaign.get(c.id, []), key=lambda x: x.role_name.value)
                    if a.user_id
                ],
                "campaign_name": c.title,
                "campaign_status": _normalize_campaign_status(c.status).value,
                "campaign_health": str((health_by_campaign.get(c.id) or {}).get("overall_status") or "not_started"),
                "deliverables_summary": {
                    "total": len(deliverables_by_campaign.get(c.id, [])),
                    "not_started": len(
                        [
                            d
                            for d in deliverables_by_campaign.get(c.id, [])
                            if _normalize_deliverable_status(d.status) == GlobalStatus.NOT_STARTED
                        ]
                    ),
                    "in_progress": len(
                        [
                            d
                            for d in deliverables_by_campaign.get(c.id, [])
                            if _normalize_deliverable_status(d.status) in {
                                GlobalStatus.IN_PROGRESS,
                                GlobalStatus.ON_HOLD,
                                GlobalStatus.BLOCKED_CLIENT,
                                GlobalStatus.BLOCKED_INTERNAL,
                                GlobalStatus.BLOCKED_DEPENDENCY,
                            }
                        ]
                    ),
                    "done": len(
                        [
                            d
                            for d in deliverables_by_campaign.get(c.id, [])
                            if _normalize_deliverable_status(d.status) == GlobalStatus.DONE
                        ]
                    ),
                },
                "deliverables": [
                    {
                        "id": d.display_id,
                        "title": d.title,
                        "status": _normalize_deliverable_status(d.status).value,
                        "delivery_status": d.status.value,
                        "derived_status": _derived_deliverable_status(db, d),
                        "health": timeline_health.evaluate_deliverable(
                            deliverable=d,
                            campaign=c,
                            steps=[s for s in workflow_steps_by_campaign.get(c.id, []) if _step_linked_deliverable(s) == d.id],
                            efforts_by_step_id=step_efforts_by_step_id,
                        ).health,
                        "current_due": d.current_due.isoformat() if d.current_due else None,
                        "current_start": d.current_start.isoformat() if d.current_start else None,
                        "stage": _deliverable_stage_from_record(d).value,
                        "owner_user_id": d.owner_user_id,
                        "owner_initials": _initials_for_user_id(d.owner_user_id, users_by_id),
                        "campaign_name": c.title,
                    }
                    for d in sorted(
                        deliverables_by_campaign.get(c.id, []),
                        key=lambda x: (x.current_due or date.max, x.created_at),
                    )
                ],
                "work_summary": {
                    "total": len(workflow_steps_by_campaign.get(c.id, [])),
                    "not_started": len(
                        [
                            s
                            for s in workflow_steps_by_campaign.get(c.id, [])
                            if _normalize_step_status(s) == GlobalStatus.NOT_STARTED
                        ]
                    ),
                    "in_progress": len(
                        [
                            s
                            for s in workflow_steps_by_campaign.get(c.id, [])
                            if _normalize_step_status(s)
                            in {
                                GlobalStatus.IN_PROGRESS,
                                GlobalStatus.ON_HOLD,
                                GlobalStatus.BLOCKED_CLIENT,
                                GlobalStatus.BLOCKED_INTERNAL,
                                GlobalStatus.BLOCKED_DEPENDENCY,
                            }
                        ]
                    ),
                    "done": len(
                        [
                            s
                            for s in workflow_steps_by_campaign.get(c.id, [])
                            if _normalize_step_status(s) == GlobalStatus.DONE
                        ]
                    ),
                },
                "work_steps": [
                    {
                        "id": s.display_id,
                        "name": s.name,
                        "module_type": "step",
                        "stage": (
                            (
                                str(s.stage_name).strip().lower()
                                if s.stage_name and str(s.stage_name).strip().lower() in {"planning", "production", "promotion", "reporting"}
                                else (
                                    _deliverable_stage_from_record(
                                        next(
                                            (d for d in deliverables_by_campaign.get(c.id, []) if d.id == _step_linked_deliverable(s)),
                                            None,
                                        )
                                    ).value
                                    if _step_linked_deliverable(s)
                                    and next(
                                        (d for d in deliverables_by_campaign.get(c.id, []) if d.id == _step_linked_deliverable(s)),
                                        None,
                                    )
                                    else (
                                        "planning" if s.campaign_id and not _step_linked_deliverable(s) else "production"
                                    )
                                )
                            )
                        ),
                        "status": _normalize_step_status(s).value,
                        "health": timeline_health.evaluate_step(s, campaign=c).health,
                        "current_start": s.current_start.isoformat() if s.current_start else None,
                        "current_due": s.current_due.isoformat() if s.current_due else None,
                        "earliest_start_date": s.earliest_start_date.isoformat() if s.earliest_start_date else None,
                        "planned_work_date": s.planned_work_date.isoformat() if s.planned_work_date else None,
                        "completion_date": s.actual_done.isoformat() if s.actual_done else None,
                        "next_owner_user_id": s.next_owner_user_id,
                        "owner_initials": _initials_for_user_id(s.next_owner_user_id, users_by_id),
                        "participant_initials": _participant_initials_for_step(s, step_efforts_by_step_id, users_by_id),
                        "deliverable_title": next(
                            (d.title for d in deliverables_by_campaign.get(c.id, []) if d.id == _step_linked_deliverable(s)),
                            None,
                        ),
                    }
                    for s in sorted(
                        workflow_steps_by_campaign.get(c.id, []),
                        key=lambda x: (x.current_due or date.max, x.created_at),
                    )
                ],
                "created_at": c.created_at.isoformat(),
            }
        for c in campaigns
        if _campaign_visible_for_actor(c)
    ]
    if status:
        needle_status = status.strip().lower()
        all_items = [
            i
            for i in all_items
            if i["status"] == needle_status or str(i.get("delivery_status", "")).lower() == needle_status
        ]
    if owner:
        all_items = [i for i in all_items if owner in i["owner_user_ids"]]
    if q:
        needle = q.strip().lower()
        all_items = [
            i
            for i in all_items
            if needle in " ".join([i["id"], i["title"], i["type"], i["tier"], i["status"]]).lower()
        ]
    total = len(all_items)
    items = all_items[offset : offset + limit]
    for i in items:
        i.pop("campaign_internal_id", None)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.patch("/campaigns/{campaign_id}/assignments")
def update_campaign_assignments(campaign_id: str, payload: CampaignAssignmentsUpdateIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    can_manage_assignments = _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_assignments",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    )
    can_manage_step = _actor_has_control_permission(
        db,
        actor,
        "manage_step",
        fallback_allowed_roles={RoleName.CM, RoleName.CC, RoleName.CCS, RoleName.HEAD_OPS, RoleName.ADMIN},
    )
    if not (can_manage_assignments or can_manage_step):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    updates = [
        (RoleName.AM, payload.am_user_id),
        (RoleName.CM, payload.cm_user_id),
        (RoleName.CC, payload.cc_user_id),
        (RoleName.CCS, payload.ccs_user_id),
        (RoleName.DN, payload.dn_user_id),
        (RoleName.MM, payload.mm_user_id),
    ]

    required_team_by_slot = {
        RoleName.AM: TeamName.SALES,
        RoleName.CM: TeamName.CLIENT_SERVICES,
        RoleName.CC: TeamName.EDITORIAL,
        RoleName.CCS: TeamName.EDITORIAL,
        RoleName.DN: TeamName.MARKETING,
        RoleName.MM: TeamName.MARKETING,
    }

    by_role = {
        a.role_name: a
        for a in db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    }
    old_assignment_by_role: dict[RoleName, str | None] = {
        role_name: (by_role.get(role_name).user_id if by_role.get(role_name) else None)
        for role_name, _ in updates
    }

    for role_name, user_id in updates:
        if user_id:
            exists = db.get(User, user_id)
            if not exists:
                raise HTTPException(status_code=400, detail=f"user not found for role {role_name.value}")
            required_team = required_team_by_slot.get(role_name)
            if required_team and exists.primary_team != required_team:
                raise HTTPException(
                    status_code=400,
                    detail=f"user must be in team {required_team.value} for role {role_name.value}",
                )
        existing = by_role.get(role_name)
        if user_id:
            if existing:
                existing.user_id = user_id
            else:
                db.add(CampaignAssignment(campaign_id=campaign.id, role_name=role_name, user_id=user_id))
        elif existing:
            db.delete(existing)

    changed_slots: list[dict[str, str | None]] = []
    for role_name, new_user_id in updates:
        old_user_id = old_assignment_by_role.get(role_name)
        if old_user_id != new_user_id:
            changed_slots.append(
                {
                    "slot": role_name.value,
                    "old_user_id": old_user_id,
                    "new_user_id": new_user_id,
                }
            )

    cascade_deliverables_updated = 0
    cascade_steps_updated = 0
    cascade_by_slot: dict[str, dict[str, int]] = {}
    if payload.cascade_owner_updates and changed_slots:
        campaign_deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
        deliverable_ids = [d.id for d in campaign_deliverables]
        if deliverable_ids:
            relevant_steps = db.scalars(
                select(WorkflowStep).where(
                    or_(
                        WorkflowStep.campaign_id == campaign.id,
                        WorkflowStep.linked_deliverable_id.in_(deliverable_ids),
                    )
                )
            ).all()
        else:
            relevant_steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()

        role_lanes_by_deliverable: dict[str, set[RoleName]] = {}
        for step in relevant_steps:
            linked = _step_linked_deliverable(step)
            if not linked:
                continue
            role_lanes_by_deliverable.setdefault(linked, set()).add(_assignment_role_lane(step.owner_role))

        for slot_change in changed_slots:
            slot = str(slot_change.get("slot") or "")
            new_user_id = slot_change.get("new_user_id")
            slot_role = RoleName(slot)
            slot_lane = _assignment_role_lane(slot_role)
            slot_deliverables_updated = 0
            slot_steps_updated = 0

            for deliverable in campaign_deliverables:
                lanes = role_lanes_by_deliverable.get(deliverable.id, set())
                if not _deliverable_matches_slot_lane(deliverable, slot_lane, lanes):
                    continue
                if deliverable.owner_user_id == new_user_id:
                    continue
                deliverable.owner_user_id = new_user_id
                slot_deliverables_updated += 1

            for step in relevant_steps:
                if _assignment_role_lane(step.owner_role) != slot_lane:
                    continue
                if step.next_owner_user_id == new_user_id:
                    continue
                step.next_owner_user_id = new_user_id
                slot_steps_updated += 1

            if slot_deliverables_updated or slot_steps_updated:
                cascade_by_slot[slot] = {
                    "deliverables": slot_deliverables_updated,
                    "steps": slot_steps_updated,
                }
            cascade_deliverables_updated += slot_deliverables_updated
            cascade_steps_updated += slot_steps_updated

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_assignments_updated",
            meta_json={
                "campaign_id": campaign.display_id,
                "am_user_id": payload.am_user_id,
                "cm_user_id": payload.cm_user_id,
                "cc_user_id": payload.cc_user_id,
                "ccs_user_id": payload.ccs_user_id,
                "dn_user_id": payload.dn_user_id,
                "mm_user_id": payload.mm_user_id,
                "changed_slots": changed_slots,
                "cascade_owner_updates": bool(payload.cascade_owner_updates),
                "cascade_counts": {
                    "deliverables": cascade_deliverables_updated,
                    "steps": cascade_steps_updated,
                    "by_slot": cascade_by_slot,
                },
            },
        )
    )

    assignment_by_role = {
        role_name: user_id for role_name, user_id in updates if user_id
    }
    campaign_steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()
    step_ids = [s.id for s in campaign_steps]
    if step_ids:
        step_efforts = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
        for effort in step_efforts:
            effort.assigned_user_id = assignment_by_role.get(effort.role_name)

    db.commit()

    refreshed = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    return {
        "campaign_id": campaign.display_id,
        "assignments": {a.role_name.value: a.user_id for a in refreshed},
        "cascade_applied": bool(payload.cascade_owner_updates),
        "updated_deliverables_count": int(cascade_deliverables_updated),
        "updated_steps_count": int(cascade_steps_updated),
        "updated_by_slot": cascade_by_slot,
    }


@router.patch("/campaigns/{campaign_id}/status")
def update_campaign_status(campaign_id: str, payload: CampaignStatusUpdateIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_status",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    old_status = _normalize_campaign_status(campaign.status).value
    new_status = _normalize_campaign_status(payload.status).value
    if new_status == old_status:
        return {
            "campaign_id": campaign.display_id,
            "status": old_status,
            "status_source": str(campaign.status_source.value if hasattr(campaign.status_source, "value") else campaign.status_source or "derived"),
        }

    StatusRollupService(db).set_manual_campaign_status(campaign, new_status, payload.actor_user_id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_status_updated",
            meta_json={
                "campaign_id": campaign.display_id,
                "old_status": old_status,
                "new_status": new_status,
            },
        )
    )
    db.commit()
    return {
        "campaign_id": campaign.display_id,
        "status": new_status,
        "status_source": str(campaign.status_source.value if hasattr(campaign.status_source, "value") else campaign.status_source),
    }


@router.post("/campaigns/{campaign_id}/status/cascade")
def bulk_update_campaign_descendant_status(campaign_id: str, payload: CampaignDescendantStatusBulkIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    actor = AuthzService(db).actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_status",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")

    status = str(payload.status or "").strip().lower()
    allowed = {"not_started", "in_progress", "on_hold", "blocked_client", "blocked_internal", "blocked_dependency", "done", "cancelled"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="unsupported status for bulk cascade")

    steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()
    stage_ids = sorted({s.stage_id for s in steps if s.stage_id})
    required_phrase = f"CASCADE {campaign.display_id}"
    if not payload.dry_run and str(payload.confirmation_phrase or "").strip() != required_phrase:
        raise HTTPException(status_code=400, detail=f"confirmation_phrase must exactly match '{required_phrase}'")

    preview = {
        "campaign_id": campaign.display_id,
        "requested_status": status,
        "steps_to_update": len(steps),
        "stages_impacted": len(stage_ids),
        "confirmation_required": required_phrase,
    }
    if payload.dry_run:
        return {"dry_run": True, **preview}

    engine = WorkflowEngineService(db)
    for step in steps:
        engine.manage_step(
            step_id=step.id,
            actor_user_id=payload.actor_user_id,
            status=status,
        )
    StatusRollupService(db).reset_campaign_to_derived(campaign)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_descendant_status_cascade",
            meta_json=preview,
        )
    )
    db.commit()
    return {"dry_run": False, **preview}


@router.patch("/campaigns/{campaign_id}/dates")
def update_campaign_dates(campaign_id: str, payload: CampaignDatesUpdateIn, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_dates",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions")
    if not payload.planned_start_iso and not payload.planned_end_iso:
        raise HTTPException(status_code=400, detail="at least one date is required")

    calendar = build_default_working_calendar()
    old_start = campaign.planned_start_date
    old_end = campaign.planned_end_date

    if payload.planned_start_iso:
        try:
            requested_start = date.fromisoformat(payload.planned_start_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid planned_start_iso; expected YYYY-MM-DD") from exc
        campaign.planned_start_date = calendar.next_working_day_on_or_after(requested_start)

    if payload.planned_end_iso:
        try:
            requested_end = date.fromisoformat(payload.planned_end_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid planned_end_iso; expected YYYY-MM-DD") from exc
        campaign.planned_end_date = calendar.next_working_day_on_or_after(requested_end)

    if campaign.planned_start_date and campaign.planned_end_date and campaign.planned_end_date < campaign.planned_start_date:
        campaign.planned_end_date = campaign.planned_start_date

    milestones_reanchored = MilestoneService(db).reanchor_campaign_milestones(campaign)

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="campaign",
            entity_id=campaign.id,
            action="campaign_dates_updated",
            meta_json={
                "campaign_id": campaign.display_id,
                "old_start": old_start.isoformat() if old_start else None,
                "old_end": old_end.isoformat() if old_end else None,
                "new_start": campaign.planned_start_date.isoformat() if campaign.planned_start_date else None,
                "new_end": campaign.planned_end_date.isoformat() if campaign.planned_end_date else None,
            },
        )
    )
    db.commit()
    return {
        "campaign_id": campaign.display_id,
        "planned_start_date": campaign.planned_start_date.isoformat() if campaign.planned_start_date else None,
        "planned_end_date": campaign.planned_end_date.isoformat() if campaign.planned_end_date else None,
        "milestones_reanchored": milestones_reanchored,
    }


@router.get("/campaigns/{campaign_id}/health")
def campaign_health(campaign_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
    deliverable_ids = [d.id for d in deliverables]
    steps = db.scalars(
        select(WorkflowStep).where(
            (WorkflowStep.campaign_id == campaign.id)
            | (WorkflowStep.linked_deliverable_id.in_(deliverable_ids))
        )
    ).all()
    stages = db.scalars(select(Stage).where(Stage.campaign_id == campaign.id).order_by(Stage.name.asc())).all()
    assignments = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    step_ids = [s.id for s in steps]
    efforts: dict[str, list[WorkflowStepEffort]] = {}
    if step_ids:
        for e in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts.setdefault(e.workflow_step_id, []).append(e)
    timeline_health = TimelineHealthService(db)
    campaign_eval, derived_stage = timeline_health.evaluate_campaign(
        campaign=campaign,
        deliverables=deliverables,
        steps=steps,
        efforts_by_step_id=efforts,
        assignments=assignments,
        stages=stages,
    )
    health_service = CampaignHealthService(db)
    health = health_service.evaluate_campaign(campaign)
    return {
        "campaign_id": campaign.display_id,
        "campaign_internal_id": campaign.id,
        "title": campaign.title,
        "type": campaign.campaign_type.value,
        "tier": campaign.tier,
        "overall_status": campaign_eval.health,
        "health_reason": campaign_eval.health_reason,
        "buffer_working_days_remaining": campaign_eval.buffer_working_days_remaining,
        "is_not_due": campaign_eval.is_not_due,
        "derived_stage": derived_stage,
        "worst_signal": health.worst_signal,
        "dimension_scores": health.dimension_scores,
        "next_action": health.next_action,
        "checkpoint_health": health.checkpoint_health,
        "warnings": health.warnings,
    }


@router.get("/deliverables")
def list_deliverables(
    limit: int = 25,
    offset: int = 0,
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    items = db.scalars(select(Deliverable).order_by(Deliverable.created_at.desc())).all()
    campaign_ids = sorted({
        d.campaign_id
        for d in items
        if d.campaign_id
    })
    campaigns_by_id = {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()} if campaign_ids else {}
    owner_ids = sorted({d.owner_user_id for d in items if d.owner_user_id})
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(owner_ids))).all()} if owner_ids else {}
    deliverable_ids = [d.id for d in items]
    open_windows_by_deliverable: dict[str, list[ReviewWindow]] = {}
    if deliverable_ids:
        rows = db.scalars(
            select(ReviewWindow).where(
                ReviewWindow.deliverable_id.in_(deliverable_ids),
                ReviewWindow.status == ReviewWindowStatus.OPEN,
            )
        ).all()
        for row in rows:
            open_windows_by_deliverable.setdefault(row.deliverable_id, []).append(row)
    steps = db.scalars(
        select(WorkflowStep).where(
            WorkflowStep.linked_deliverable_id.in_(deliverable_ids)
        )
    ).all() if deliverable_ids else []
    steps_by_deliverable: dict[str, list[WorkflowStep]] = {}
    for s in steps:
        linked = _step_linked_deliverable(s)
        if linked:
            steps_by_deliverable.setdefault(linked, []).append(s)
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if steps:
        step_ids = [s.id for s in steps]
        for e in db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all():
            efforts_by_step.setdefault(e.workflow_step_id, []).append(e)
    timeline_health = TimelineHealthService(db)
    all_items = [
            {
                "id": d.display_id,
                "deliverable_internal_id": d.id,
                "campaign_id": (
                    campaigns_by_id.get(d.campaign_id).display_id
                    if d.campaign_id and campaigns_by_id.get(d.campaign_id)
                    else None
                ),
                "campaign_name": (
                    campaigns_by_id.get(d.campaign_id).title
                    if d.campaign_id and campaigns_by_id.get(d.campaign_id)
                    else None
                ),
                "type": d.deliverable_type.value,
                "module_type": "deliverable",
                "status": _normalize_deliverable_status(d.status).value,
                "delivery_status": d.status.value,
                "derived_status": _derived_deliverable_status(db, d),
                "health": timeline_health.evaluate_deliverable(
                    deliverable=d,
                    campaign=campaigns_by_id.get(d.campaign_id) if d.campaign_id else None,
                    steps=steps_by_deliverable.get(d.id, []),
                    efforts_by_step_id=efforts_by_step,
                ).health,
                "stage": _deliverable_stage_from_record(d).value,
                "title": d.title,
                "owner_user_id": d.owner_user_id,
                "owner_initials": _initials_for_user_id(d.owner_user_id, users_by_id),
                "current_due": d.current_due.isoformat() if d.current_due else None,
                "current_start": d.current_start.isoformat() if d.current_start else None,
                "awaiting_internal_review_since": (
                    d.awaiting_internal_review_since.isoformat() if d.awaiting_internal_review_since else None
                ),
                "awaiting_client_review_since": (
                    d.awaiting_client_review_since.isoformat() if d.awaiting_client_review_since else None
                ),
                "internal_review_stall_threshold_days": d.internal_review_stall_threshold_days,
                "client_review_stall_threshold_days": d.client_review_stall_threshold_days,
                "ready_to_publish_by_user_id": d.ready_to_publish_by_user_id,
                "internal_review_rounds": d.internal_review_rounds,
                "client_review_rounds": d.client_review_rounds,
                "amend_rounds": d.amend_rounds,
                "review_windows": [
                    {
                        "id": w.display_id,
                        "type": w.window_type.value,
                        "status": w.status.value,
                        "window_start": w.window_start.isoformat(),
                        "window_due": w.window_due.isoformat(),
                        "round_number": w.round_number,
                    }
                    for w in sorted(
                        open_windows_by_deliverable.get(d.id, []),
                        key=lambda x: (x.window_due, x.created_at),
                    )
                ],
            }
            for d in items
    ]
    if status:
        all_items = [i for i in all_items if i["status"] == status]
    if q:
        needle = q.strip().lower()
        all_items = [
            i
            for i in all_items
            if needle in " ".join([i["id"], i["title"], i["type"], i["status"]]).lower()
        ]
    total = len(all_items)
    paged = all_items[offset : offset + limit]
    for i in paged:
        i.pop("deliverable_internal_id", None)
    return {"items": paged, "total": total, "limit": limit, "offset": offset}


@router.get("/reviews/queue")
def reviews_queue(actor_user_id: str, role: str, db: Session = Depends(get_db)):
    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    try:
        role_name = RoleName(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid role") from exc
    if role_name not in actor.roles and RoleName.ADMIN not in actor.roles:
        raise HTTPException(status_code=403, detail="actor does not hold selected role")

    windows = db.scalars(select(ReviewWindow).where(ReviewWindow.status == ReviewWindowStatus.OPEN)).all()
    deliverables = {d.id: d for d in db.scalars(select(Deliverable)).all()}
    campaigns = {c.id: c for c in db.scalars(select(Campaign)).all()}
    assignments = db.scalars(select(CampaignAssignment)).all()
    campaign_members: dict[str, set[str]] = {}
    for a in assignments:
        campaign_members.setdefault(a.campaign_id, set()).add(a.user_id)

    grouped = {"awaiting_internal_review": [], "awaiting_client_review": [], "changes_requested": []}
    for w in windows:
        d = deliverables.get(w.deliverable_id)
        if not d:
            continue
        campaign = campaigns.get(d.campaign_id) if d.campaign_id else None
        if campaign and actor_user_id not in campaign_members.get(campaign.id, set()) and RoleName.ADMIN not in actor.roles and RoleName.HEAD_OPS not in actor.roles:
            continue
        item = {
            "window_id": w.display_id,
            "window_type": w.window_type.value,
            "round_number": w.round_number,
            "deliverable_id": d.display_id,
            "deliverable_title": d.title,
            "deliverable_status": d.status.value,
            "campaign_id": campaign.display_id if campaign else None,
            "campaign_title": campaign.title if campaign else None,
            "window_start": w.window_start.isoformat(),
            "window_due": w.window_due.isoformat(),
            "age_days": max((date.today() - w.window_start).days, 0),
        }
        if w.window_type == ReviewWindowType.INTERNAL_REVIEW:
            grouped["awaiting_internal_review"].append(item)
        elif w.window_type == ReviewWindowType.CLIENT_REVIEW:
            grouped["awaiting_client_review"].append(item)
        elif w.window_type == ReviewWindowType.AMENDS:
            grouped["changes_requested"].append(item)

    return {
        "role": role_name.value,
        "summary": {k: len(v) for k, v in grouped.items()},
        "queues": grouped,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/campaigns/{campaign_id}/workspace")
def campaign_workspace(campaign_id: str, db: Session = Depends(get_db)):
    campaign = _resolve_by_identifier(db, Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")
    StageIntegrityService(db).reconcile_campaign(campaign.id)
    timeline_health = TimelineHealthService(db)
    scope = db.get(Deal, campaign.deal_id) if campaign.deal_id else None

    deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
    assignment_rows = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
    assignments = {row.role_name.value: row.user_id for row in assignment_rows}
    assignment_user_ids = sorted({row.user_id for row in assignment_rows if row.user_id})
    deliverable_ids = [d.id for d in deliverables]
    review_windows = (
        db.scalars(select(ReviewWindow).where(ReviewWindow.deliverable_id.in_(deliverable_ids))).all()
        if deliverable_ids
        else []
    )
    steps = db.scalars(
        select(WorkflowStep).where(
            (WorkflowStep.campaign_id == campaign.id)
            | (WorkflowStep.linked_deliverable_id.in_(deliverable_ids))
        )
    ).all()
    stages = db.scalars(select(Stage).where(Stage.campaign_id == campaign.id).order_by(Stage.name.asc())).all()
    milestones = db.scalars(
        select(Milestone)
        .where(Milestone.campaign_id == campaign.id)
        .order_by(Milestone.current_target_date.asc())
    ).all()
    system_risks = db.scalars(select(SystemRisk).where(SystemRisk.campaign_id == campaign.id, SystemRisk.is_open.is_(True))).all()
    manual_risks = db.scalars(select(ManualRisk).where(ManualRisk.campaign_id == campaign.id, ManualRisk.is_open.is_(True))).all()
    reviews = db.scalars(select(Review).where(Review.deliverable_id.in_(deliverable_ids)).order_by(Review.created_at.desc())).all() if deliverable_ids else []
    step_ids = [s.id for s in steps]
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    if step_ids:
        step_efforts = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
        for effort in step_efforts:
            efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
    else:
        step_efforts = []
    user_ids = set(assignment_user_ids).union({
        s.next_owner_user_id
        for s in steps
        if s.next_owner_user_id
    }).union(
        {
            e.assigned_user_id
            for e in step_efforts
            if e.assigned_user_id
        }
    ).union(
        {
            d.owner_user_id
            for d in deliverables
            if d.owner_user_id
        }
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(sorted(user_ids)))).all()} if user_ids else {}
    milestone_start, milestone_due = _campaign_timeframe_from_milestones(milestones)
    timeframe_start = campaign.planned_start_date.isoformat() if campaign.planned_start_date else milestone_start
    timeframe_due = campaign.planned_end_date.isoformat() if campaign.planned_end_date else milestone_due
    activity = db.scalars(
        select(ActivityLog)
        .where(
            ((ActivityLog.entity_type == "deliverable") & (ActivityLog.entity_id.in_(deliverable_ids)))
            | ((ActivityLog.entity_type == "workflow_step") & (ActivityLog.entity_id.in_(step_ids)))
        )
        .order_by(ActivityLog.created_at.desc())
    ).all() if (deliverable_ids or step_ids) else []

    deliverable_status_counts: dict[str, int] = {}
    windows_by_deliverable: dict[str, list[ReviewWindow]] = {}
    for w in review_windows:
        windows_by_deliverable.setdefault(w.deliverable_id, []).append(w)
    for d in deliverables:
        deliverable_status_counts[d.status.value] = deliverable_status_counts.get(d.status.value, 0) + 1

    review_counts = {"pending_internal": 0, "pending_client": 0, "changes_requested": 0}
    for d in deliverables:
        if d.status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            review_counts["pending_internal"] += 1
        if d.status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            review_counts["pending_client"] += 1
        if d.status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
            review_counts["changes_requested"] += 1

    sprint_summary = []
    sprint_label = f"S{campaign.demand_sprint_number}" if campaign.is_demand_sprint and campaign.demand_sprint_number else "Campaign"
    deliverables_by_id = {d.id: d for d in deliverables}
    steps_by_group_label: dict[str, list[WorkflowStep]] = {}
    for st in steps:
        key = sprint_label
        steps_by_group_label.setdefault(key, []).append(st)

    def _phase_for_step(step: WorkflowStep, deliverable: Deliverable | None) -> str:
        if step.stage_name:
            stage = step.stage_name.strip().lower()
            if stage in {"planning", "production", "promotion", "reporting"}:
                return stage
        if step.stage_id:
            stage_rec = next((s for s in stages if s.id == step.stage_id), None)
            if stage_rec and stage_rec.name:
                return str(stage_rec.name).strip().lower()
        linked_deliverable_id = _step_linked_deliverable(step)
        if step.campaign_id and not linked_deliverable_id:
            return "planning"
        if deliverable and deliverable.deliverable_type.value in {"report", "engagement_list", "lead_total"}:
            return "reporting"
        if deliverable and deliverable.deliverable_type.value == "display_asset":
            return "promotion"
        return "production"

    grouping_keys = sorted(steps_by_group_label.keys()) or [sprint_label]
    for key in grouping_keys:
        s_deliverables = [
            d for d in deliverables
            if (d.campaign_id == campaign.id and key == sprint_label)
        ]
        sections: dict[str, list[dict]] = {"planning": [], "production": [], "promotion": [], "reporting": []}
        for st in sorted(
            steps_by_group_label.get(key, []),
            key=lambda x: (
                x.current_due or date.max,
                x.created_at.date(),
            ),
        ):
            linked_deliverable_id = _step_linked_deliverable(st)
            parent_deliverable = deliverables_by_id.get(linked_deliverable_id) if linked_deliverable_id else None
            phase = _phase_for_step(st, parent_deliverable)
            sections[phase].append(
                {
                    "id": st.display_id,
                    "name": st.name,
                    "module_type": _step_module_type(st),
                    "step_kind": st.step_kind.value,
                    "status": _normalize_step_status(st).value,
                    "health": timeline_health.evaluate_step(st, campaign=campaign).health,
                    "owner_role": st.owner_role.value,
                    "next_owner_user_id": st.next_owner_user_id,
                    "owner_initials": _initials_for_user_id(st.next_owner_user_id, users_by_id),
                    "participant_initials": _participant_initials_for_step(st, efforts_by_step, users_by_id),
                    "current_start": st.current_start.isoformat() if st.current_start else None,
                    "current_due": st.current_due.isoformat() if st.current_due else None,
                    "waiting_on_type": st.waiting_on_type.value if st.waiting_on_type else None,
                    "blocker_reason": st.blocker_reason,
                    "deliverable_id": parent_deliverable.display_id if parent_deliverable else None,
                    "deliverable_title": parent_deliverable.title if parent_deliverable else None,
                    "linked_deliverable_id": parent_deliverable.display_id if parent_deliverable else None,
                    "linked_deliverable_title": parent_deliverable.title if parent_deliverable else None,
                    "stage_id": st.stage_id,
                    "effort_allocations": [
                        {
                            "role": e.role_name.value,
                            "hours": float(e.hours),
                            "assigned_user_id": e.assigned_user_id,
                        }
                        for e in sorted(efforts_by_step.get(st.id, []), key=lambda x: (x.role_name.value, x.created_at))
                    ],
                }
            )
        sections = {k: v for k, v in sections.items() if v}
        sprint_summary.append(
            {
                "id": key,
                "sprint_number": campaign.demand_sprint_number if campaign.is_demand_sprint else 1,
                "baseline_start": None,
                "current_start": None,
                "deliverables_total": len(s_deliverables),
                "deliverables_complete": len([d for d in s_deliverables if d.status == DeliverableStatus.COMPLETE]),
                "sections": sections,
            }
        )

    health_service = CampaignHealthService(db)
    health = health_service.evaluate_campaign(campaign)
    campaign_health_eval, derived_stage = timeline_health.evaluate_campaign(
        campaign=campaign,
        deliverables=deliverables,
        steps=steps,
        efforts_by_step_id=efforts_by_step,
        assignments=assignment_rows,
        stages=stages,
    )

    return {
        "campaign": {
            "id": campaign.display_id,
            "scope_id": scope.display_id if scope else None,
            "title": campaign.title,
            "type": campaign.campaign_type.value,
            "tier": campaign.tier,
            "status": _normalize_campaign_status(campaign.status).value,
            "status_source": str(campaign.status_source.value if hasattr(campaign.status_source, "value") else campaign.status_source or "derived"),
            "status_overridden_by_user_id": campaign.status_overridden_by_user_id,
            "module_type": "campaign",
            "health": campaign_health_eval.health,
            "health_reason": campaign_health_eval.health_reason,
            "buffer_working_days_remaining": campaign_health_eval.buffer_working_days_remaining,
            "is_not_due": campaign_health_eval.is_not_due,
            "timeframe_start": timeframe_start,
            "timeframe_due": timeframe_due,
            "campaign_name": campaign.title,
            "campaign_status": _normalize_campaign_status(campaign.status).value,
            "campaign_health": campaign_health_eval.health,
            "derived_stage": derived_stage,
            "is_demand_sprint": campaign.is_demand_sprint,
            "demand_sprint_number": campaign.demand_sprint_number,
            "demand_track": campaign.demand_track,
            "sprint_label": (f"S{campaign.demand_sprint_number}" if campaign.is_demand_sprint and campaign.demand_sprint_number else None),
            "assignments": assignments,
            "assigned_users": [
                {
                    "user_id": row.user_id,
                    "role": row.role_name.value,
                    "name": users_by_id.get(row.user_id).full_name if users_by_id.get(row.user_id) else None,
                    "initials": _initials_for_user_id(row.user_id, users_by_id),
                }
                for row in sorted(assignment_rows, key=lambda x: x.role_name.value)
            ],
            "assigned_user_initials": [
                _initials_for_user_id(row.user_id, users_by_id)
                for row in sorted(assignment_rows, key=lambda x: x.role_name.value)
                if row.user_id
            ],
        },
        "health_summary": {
            "overall_status": campaign_health_eval.health,
            "health_reason": campaign_health_eval.health_reason,
            "buffer_working_days_remaining": campaign_health_eval.buffer_working_days_remaining,
            "is_not_due": campaign_health_eval.is_not_due,
            "worst_signal": health.worst_signal,
            "dimension_scores": health.dimension_scores,
            "checkpoint_health": health.checkpoint_health,
            "warnings": health.warnings,
        },
        "next_action": health.next_action,
        "overview": {
            "sprints_total": max(len(sprint_summary), 1),
            "deliverables_total": len(deliverables),
            "workflow_steps_open": len([s for s in steps if s.actual_done is None]),
            "open_system_risks": len(system_risks),
            "open_manual_risks": len(manual_risks),
        },
        "sprints": sprint_summary,
        "deliverables": {
            "counts_by_status": deliverable_status_counts,
            "items": [
                {
                    "id": d.display_id,
                    "title": d.title,
                    "module_type": "deliverable",
                    "type": d.deliverable_type.value,
                    "status": _normalize_deliverable_status(d.status).value,
                    "delivery_status": d.status.value,
                    "derived_status": _derived_deliverable_status(db, d),
                    "health": timeline_health.evaluate_deliverable(
                        deliverable=d,
                        campaign=campaign,
                        steps=[s for s in steps if _step_linked_deliverable(s) == d.id],
                        efforts_by_step_id=efforts_by_step,
                    ).health,
                    "stage": _deliverable_stage_from_record(d).value,
                    "owner_user_id": d.owner_user_id,
                    "owner_initials": _initials_for_user_id(d.owner_user_id, users_by_id),
                    "current_due": d.current_due.isoformat() if d.current_due else None,
                    "current_start": d.current_start.isoformat() if d.current_start else None,
                    "internal_review_rounds": d.internal_review_rounds,
                    "client_review_rounds": d.client_review_rounds,
                    "amend_rounds": d.amend_rounds,
                    "review_windows": [
                        {
                            "id": w.display_id,
                            "type": w.window_type.value,
                            "status": w.status.value,
                            "window_start": w.window_start.isoformat(),
                            "window_due": w.window_due.isoformat(),
                            "round_number": w.round_number,
                        }
                        for w in sorted(windows_by_deliverable.get(d.id, []), key=lambda x: (x.window_start, x.created_at))
                    ],
                }
                for d in deliverables
            ],
        },
        "workflow_steps": {
            "items": [
                {
                    "id": s.display_id,
                    "name": s.name,
                    "module_type": _step_module_type(s),
                    "step_kind": s.step_kind.value,
                    "status": _normalize_step_status(s).value,
                    "health": timeline_health.evaluate_step(s, campaign=campaign).health,
                    "owner_role": s.owner_role.value,
                    "current_due": s.current_due.isoformat() if s.current_due else None,
                    "next_owner_user_id": s.next_owner_user_id,
                    "owner_initials": _initials_for_user_id(s.next_owner_user_id, users_by_id),
                    "participant_initials": _participant_initials_for_step(s, efforts_by_step, users_by_id),
                    "current_start": s.current_start.isoformat() if s.current_start else None,
                    "earliest_start_date": s.earliest_start_date.isoformat() if s.earliest_start_date else None,
                    "planned_work_date": s.planned_work_date.isoformat() if s.planned_work_date else None,
                    "completion_date": s.actual_done.isoformat() if s.actual_done else None,
                    "waiting_on_type": s.waiting_on_type.value if s.waiting_on_type else None,
                    "blocker_reason": s.blocker_reason,
                    "step_state": (
                        _normalize_step_status(s).value
                    ),
                    "stage_name": s.stage_name,
                    "stage_id": s.stage_id,
                    "effort_allocations": [
                        {
                            "role": e.role_name.value,
                            "hours": float(e.hours),
                            "assigned_user_id": e.assigned_user_id,
                        }
                        for e in sorted(efforts_by_step.get(s.id, []), key=lambda x: (x.role_name.value, x.created_at))
                    ],
                    "campaign_id": campaign.display_id,
                    "parent_type": "stage" if s.stage_id else "campaign",
                    "deliverable_id": deliverables_by_id.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                    "deliverable_title": deliverables_by_id.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                    "linked_deliverable_id": deliverables_by_id.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                    "linked_deliverable_title": deliverables_by_id.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables_by_id.get(_step_linked_deliverable(s)) else None,
                }
                for s in steps
            ]
        },
        "stages": [
            {
                "id": st.id,
                "display_id": st.display_id,
                "name": st.name,
                "status": str(st.status.value if hasattr(st.status, "value") else st.status),
                "health": str(st.health.value if hasattr(st.health, "value") else st.health),
                "baseline_start": st.baseline_start.isoformat() if st.baseline_start else None,
                "baseline_due": st.baseline_due.isoformat() if st.baseline_due else None,
                "current_start": st.current_start.isoformat() if st.current_start else None,
                "current_due": st.current_due.isoformat() if st.current_due else None,
                "actual_done": st.actual_done.isoformat() if st.actual_done else None,
                "step_count": len([x for x in steps if x.stage_id == st.id]),
            }
            for st in stages
        ],
        "reviews": {
            "counts": review_counts,
            "recent": [
                {
                    "id": r.display_id,
                    "review_type": r.review_type,
                    "status": r.status,
                    "comments": r.comments,
                    "created_at": r.created_at.isoformat(),
                }
                for r in reviews[:20]
            ],
        },
        "risks": {
            "system": [
                {"id": r.display_id, "severity": r.severity.value, "code": r.risk_code, "details": r.details}
                for r in system_risks
            ],
            "manual": [
                {"id": r.display_id, "severity": r.severity.value, "details": r.details}
                for r in manual_risks
            ],
        },
        "timeline": {
            "milestones": [
                {
                    "id": m.display_id,
                    "name": m.name,
                    "baseline_date": m.baseline_date.isoformat() if m.baseline_date else None,
                    "current_target_date": m.current_target_date.isoformat() if m.current_target_date else None,
                    "achieved_at": m.achieved_at.isoformat() if m.achieved_at else None,
                }
                for m in milestones[:50]
            ],
        },
        "activity": [
            {
                "id": a.display_id,
                "action": a.action,
                "created_at": a.created_at.isoformat(),
                "meta": a.meta_json,
            }
            for a in activity[:30]
        ],
    }


@router.post("/deliverables/{deliverable_id}/transition")
def transition_deliverable(deliverable_id: str, payload: DeliverableTransitionIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    campaign = _campaign_for_deliverable(db, deliverable)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_campaign_member_or_roles(
        actor=actor,
        campaign=campaign,
        member_roles={RoleName.AM, RoleName.CM, RoleName.CC, RoleName.CCS},
        fallback_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    )

    try:
        to_status = DeliverableStatus(payload.to_status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid to_status") from exc

    updated = DeliverableWorkflowService(db).transition(
        deliverable=deliverable,
        to_status=to_status,
        actor_user_id=payload.actor_user_id,
        actor_roles=actor.roles,
        comment=payload.comment,
    )
    DeliverableDerivationService(db).recompute_operational_stage_status(updated)
    db.commit()
    health_payload = _evaluate_deliverable_health(db, updated)
    return {
        "id": updated.display_id,
        "status": _normalize_deliverable_status(updated.status).value,
        "delivery_status": updated.status.value,
        "derived_status": _derived_deliverable_status(db, updated),
        "health": health_payload["health"],
        "health_reason": health_payload["health_reason"],
        "buffer_working_days_remaining": health_payload["buffer_working_days_remaining"],
        "is_not_due": health_payload["is_not_due"],
        "stage": _deliverable_stage_from_record(updated).value,
        "ready_to_publish_at": updated.ready_to_publish_at,
        "actual_done": updated.actual_done,
    }


@router.delete("/deliverables/{deliverable_id}")
def delete_deliverable(deliverable_id: str, actor_user_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "delete_deliverable",
        fallback_allowed_roles={RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="not permitted to delete deliverable")

    deleted = _delete_deliverable_graph(db, deliverable.id)
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_deleted",
            meta_json={"deliverable_id": deliverable.display_id, "deleted_counts": deleted},
        )
    )
    db.commit()
    return {"deleted": True, "deliverable_id": deliverable.display_id, "counts": deleted}


@router.post("/deliverables/{deliverable_id}/override-due")
def override_deliverable_due(deliverable_id: str, payload: DeliverableDueUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "override_step_due",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit due dates")

    try:
        requested = date.fromisoformat(payload.current_due_iso)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid current_due_iso; expected YYYY-MM-DD") from exc

    calendar = build_default_working_calendar()
    adjusted_due = calendar.next_working_day_on_or_after(requested)
    old_due = deliverable.current_due
    deliverable.current_due = adjusted_due
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_due_overridden",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_due": old_due.isoformat() if old_due else None,
                "new_due": adjusted_due.isoformat(),
                "reason_code": payload.reason_code,
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "current_due": adjusted_due.isoformat(),
        "reason_code": payload.reason_code,
    }


@router.patch("/deliverables/{deliverable_id}/dates")
def update_deliverable_dates(deliverable_id: str, payload: DeliverableDatesUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_deliverable_dates",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit deliverable dates")
    if not payload.current_start_iso and not payload.current_due_iso:
        raise HTTPException(status_code=400, detail="at least one date is required")

    calendar = build_default_working_calendar()
    old_start = deliverable.current_start
    old_due = deliverable.current_due

    if payload.current_start_iso:
        try:
            requested_start = date.fromisoformat(payload.current_start_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid current_start_iso; expected YYYY-MM-DD") from exc
        deliverable.current_start = calendar.next_working_day_on_or_after(requested_start)

    if payload.current_due_iso:
        try:
            requested_due = date.fromisoformat(payload.current_due_iso)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid current_due_iso; expected YYYY-MM-DD") from exc
        deliverable.current_due = calendar.next_working_day_on_or_after(requested_due)

    if deliverable.current_start and deliverable.current_due and deliverable.current_due < deliverable.current_start:
        deliverable.current_due = deliverable.current_start

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_dates_updated",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_start": old_start.isoformat() if old_start else None,
                "old_due": old_due.isoformat() if old_due else None,
                "new_start": deliverable.current_start.isoformat() if deliverable.current_start else None,
                "new_due": deliverable.current_due.isoformat() if deliverable.current_due else None,
                "reason_code": payload.reason_code or "schedule_adjustment",
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "current_start": deliverable.current_start.isoformat() if deliverable.current_start else None,
        "current_due": deliverable.current_due.isoformat() if deliverable.current_due else None,
        "reason_code": payload.reason_code or "schedule_adjustment",
    }


@router.patch("/deliverables/{deliverable_id}/stage")
def update_deliverable_stage(deliverable_id: str, payload: DeliverableStageUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "edit_deliverable_stage",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit deliverable stage")

    try:
        new_stage = DeliverableStage(payload.stage.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid stage") from exc

    old_stage = _deliverable_stage_from_record(deliverable).value
    deliverable.stage = new_stage
    deliverable.operational_stage_status = new_stage
    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_stage_updated",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_stage": old_stage,
                "new_stage": new_stage.value,
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "stage": new_stage.value,
    }


@router.patch("/deliverables/{deliverable_id}/owner")
def update_deliverable_owner(deliverable_id: str, payload: DeliverableOwnerUpdateIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_deliverable_owner",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient role permissions to edit deliverable owner")

    old_owner = deliverable.owner_user_id
    new_owner = payload.owner_user_id or None
    if new_owner:
        u = db.get(User, new_owner)
        if not u:
            raise HTTPException(status_code=400, detail="owner_user_id not found")
    deliverable.owner_user_id = new_owner

    users_by_id: dict[str, User] = {}
    if deliverable.owner_user_id:
        owner = db.get(User, deliverable.owner_user_id)
        if owner:
            users_by_id[owner.id] = owner
    owner_initials = _initials_for_user_id(deliverable.owner_user_id, users_by_id)

    db.add(
        ActivityLog(
            display_id=PublicIdService(db).next_id(ActivityLog, "ACT"),
            actor_user_id=payload.actor_user_id,
            entity_type="deliverable",
            entity_id=deliverable.id,
            action="deliverable_owner_updated",
            meta_json={
                "deliverable_display_id": deliverable.display_id,
                "old_owner_user_id": old_owner,
                "new_owner_user_id": deliverable.owner_user_id,
            },
        )
    )
    db.commit()
    return {
        "id": deliverable.display_id,
        "owner_user_id": deliverable.owner_user_id,
        "owner_initials": owner_initials,
    }


@router.get("/deliverables/{deliverable_id}/history")
def deliverable_history(deliverable_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")

    activity = db.scalars(
        select(ActivityLog)
        .where(ActivityLog.entity_type == "deliverable", ActivityLog.entity_id == deliverable.id)
        .order_by(ActivityLog.created_at.desc())
    ).all()
    reviews = db.scalars(
        select(Review)
        .where(Review.deliverable_id == deliverable.id)
        .order_by(Review.created_at.desc())
    ).all()

    return {
        "deliverable": {
            "id": deliverable.display_id,
            "title": deliverable.title,
            "status": _normalize_deliverable_status(deliverable.status).value,
            "delivery_status": deliverable.status.value,
            "derived_status": _derived_deliverable_status(db, deliverable),
            "health": _evaluate_deliverable_health(db, deliverable)["health"],
            "stage": _deliverable_stage_from_record(deliverable).value,
            "internal_review_rounds": deliverable.internal_review_rounds,
            "client_review_rounds": deliverable.client_review_rounds,
            "amend_rounds": deliverable.amend_rounds,
            "awaiting_internal_review_since": (
                deliverable.awaiting_internal_review_since.isoformat() if deliverable.awaiting_internal_review_since else None
            ),
            "awaiting_client_review_since": (
                deliverable.awaiting_client_review_since.isoformat() if deliverable.awaiting_client_review_since else None
            ),
            "internal_review_stall_threshold_days": deliverable.internal_review_stall_threshold_days,
            "client_review_stall_threshold_days": deliverable.client_review_stall_threshold_days,
        },
        "activity": [
            {
                "id": a.display_id,
                "action": a.action,
                "created_at": a.created_at.isoformat(),
                "meta": a.meta_json,
            }
            for a in activity
        ],
        "reviews": [
            {
                "id": r.display_id,
                "review_type": r.review_type,
                "status": r.status,
                "comments": r.comments,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }


@router.get("/deliverables/{deliverable_id}/review-windows")
def deliverable_review_windows(deliverable_id: str, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")
    windows = DeliverableWorkflowService(db).list_windows(deliverable)
    round_events = db.scalars(
        select(ReviewRoundEvent)
        .where(ReviewRoundEvent.deliverable_id == deliverable.id)
        .order_by(ReviewRoundEvent.event_at.desc(), ReviewRoundEvent.created_at.desc())
    ).all()
    return {
        "deliverable": {
            "id": deliverable.display_id,
            "title": deliverable.title,
            "status": _normalize_deliverable_status(deliverable.status).value,
            "delivery_status": deliverable.status.value,
            "derived_status": _derived_deliverable_status(db, deliverable),
            "health": _evaluate_deliverable_health(db, deliverable)["health"],
            "stage": _deliverable_stage_from_record(deliverable).value,
            "internal_review_rounds": deliverable.internal_review_rounds,
            "client_review_rounds": deliverable.client_review_rounds,
            "amend_rounds": deliverable.amend_rounds,
        },
        "windows": [
            {
                "id": w.display_id,
                "type": w.window_type.value,
                "status": w.status.value,
                "window_start": w.window_start.isoformat(),
                "window_due": w.window_due.isoformat(),
                "completed_at": w.completed_at.isoformat() if w.completed_at else None,
                "round_number": w.round_number,
            }
            for w in windows
        ],
        "round_events": [
            {
                "id": e.display_id,
                "event_type": e.event_type.value,
                "round_number": e.round_number,
                "event_at": e.event_at.isoformat(),
                "actor_user_id": e.actor_user_id,
                "note": e.note,
                "source": e.source,
            }
            for e in round_events
        ],
    }


@router.post("/deliverables/{deliverable_id}/review-rounds/increment")
def increment_review_round(deliverable_id: str, payload: ReviewRoundIncrementIn, db: Session = Depends(get_db)):
    deliverable = _resolve_by_identifier(db, Deliverable, deliverable_id)
    if not deliverable:
        raise HTTPException(status_code=404, detail="deliverable not found")
    authz = AuthzService(db)
    actor = authz.actor(payload.actor_user_id)
    authz.require_any(actor, {RoleName.AM, RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN})
    result = DeliverableWorkflowService(db).increment_round(
        deliverable=deliverable,
        round_type=payload.round_type,
        actor_user_id=payload.actor_user_id,
        note=payload.note,
    )
    db.commit()
    return result


@router.get("/workflow-steps")
def list_workflow_steps(db: Session = Depends(get_db)):
    items = db.scalars(select(WorkflowStep).order_by(WorkflowStep.created_at.asc())).all()
    step_ids = [s.id for s in items]
    efforts = db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all() if step_ids else []
    efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
    for effort in efforts:
        efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
    deliverable_ids = {_step_linked_deliverable(s) for s in items if _step_linked_deliverable(s)}
    deliverables = (
        {d.id: d for d in db.scalars(select(Deliverable).where(Deliverable.id.in_(deliverable_ids))).all()}
        if deliverable_ids
        else {}
    )
    campaign_ids = {d.campaign_id for d in deliverables.values() if d.campaign_id}.union({s.campaign_id for s in items if s.campaign_id})
    campaigns = {c.id: c for c in db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()} if campaign_ids else {}
    owner_ids = {s.next_owner_user_id for s in items if s.next_owner_user_id}
    participant_ids = {e.assigned_user_id for e in efforts if e.assigned_user_id}
    user_ids = sorted(owner_ids.union(participant_ids))
    owners = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    timeline_health = TimelineHealthService(db)

    def _step_state(step: WorkflowStep) -> str:
        if step.actual_done:
            return "done"
        if step.waiting_on_type:
            return f"blocked_{step.waiting_on_type.value}"
        if step.actual_start:
            return "in_progress"
        return "not_started"

    return {
        "items": [
            {
                "id": s.display_id,
                "name": s.name,
                "module_type": _step_module_type(s),
                "step_kind": s.step_kind.value,
                "owner_role": s.owner_role.value,
                "status": _normalize_step_status(s).value,
                "health": timeline_health.evaluate_step(
                    s,
                    campaign=(
                        campaigns.get(s.campaign_id)
                        or (
                            campaigns.get(deliverables.get(_step_linked_deliverable(s)).campaign_id)
                            if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) and deliverables.get(_step_linked_deliverable(s)).campaign_id
                            else None
                        )
                    ),
                ).health,
                "step_state": _step_state(s),
                "current_start": s.current_start.isoformat() if s.current_start else None,
                "current_due": s.current_due.isoformat() if s.current_due else None,
                "earliest_start_date": s.earliest_start_date.isoformat() if s.earliest_start_date else None,
                "planned_work_date": s.planned_work_date.isoformat() if s.planned_work_date else None,
                "completion_date": s.actual_done.isoformat() if s.actual_done else None,
                "actual_done": s.actual_done.isoformat() if s.actual_done else None,
                "parent_type": "stage" if s.stage_id else "campaign",
                "next_owner_user_id": s.next_owner_user_id,
                "next_owner_name": owners.get(s.next_owner_user_id).full_name if owners.get(s.next_owner_user_id) else None,
                "owner_initials": _initials_for_user_id(s.next_owner_user_id, owners),
                "participant_initials": _participant_initials_for_step(s, efforts_by_step, owners),
                "waiting_on_type": s.waiting_on_type.value if s.waiting_on_type else None,
                "waiting_on_user_id": s.waiting_on_user_id,
                "blocker_reason": s.blocker_reason,
                "deliverable_id": deliverables.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "deliverable_title": deliverables.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "linked_deliverable_id": deliverables.get(_step_linked_deliverable(s)).display_id if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "linked_deliverable_title": deliverables.get(_step_linked_deliverable(s)).title if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) else None,
                "campaign_id": (
                    campaigns.get(s.campaign_id).display_id
                    if s.campaign_id and campaigns.get(s.campaign_id)
                    else (
                        campaigns.get(deliverables.get(_step_linked_deliverable(s)).campaign_id).display_id
                        if _step_linked_deliverable(s) and deliverables.get(_step_linked_deliverable(s)) and deliverables.get(_step_linked_deliverable(s)).campaign_id and campaigns.get(deliverables.get(_step_linked_deliverable(s)).campaign_id)
                        else None
                    )
                ),
                "stage_name": s.stage_name,
                "stage_id": s.stage_id,
                "effort_allocations": [
                    {
                        "role": e.role_name.value,
                        "hours": float(e.hours),
                        "assigned_user_id": e.assigned_user_id,
                    }
                    for e in sorted(efforts_by_step.get(s.id, []), key=lambda x: (x.role_name.value, x.created_at))
                ],
            }
            for s in items
        ]
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name.asc())).all()
    user_ids = [u.id for u in users]
    assignments = db.scalars(select(UserRoleAssignment).where(UserRoleAssignment.user_id.in_(user_ids))).all() if user_ids else []
    role_ids = sorted({a.role_id for a in assignments})
    roles = {r.id: r for r in db.scalars(select(Role).where(Role.id.in_(role_ids))).all()} if role_ids else {}
    roles_map: dict[str, list[str]] = {u.id: [] for u in users}
    for a in assignments:
        role = roles.get(a.role_id)
        if role:
            roles_map.setdefault(a.user_id, []).append(role.name.value)
    return {
        "items": [
            {
                "id": u.id,
                "name": u.full_name,
                "email": u.email,
                "roles": sorted(set(roles_map.get(u.id, []))),
                "primary_team": u.primary_team.value,
                "editorial_subteam": (
                    u.editorial_subteam.value if getattr(u, "editorial_subteam", None) and hasattr(u.editorial_subteam, "value")
                    else (str(u.editorial_subteam) if getattr(u, "editorial_subteam", None) else None)
                ),
                "seniority": u.seniority.value,
                "app_role": u.app_role.value,
            }
            for u in users
        ]
    }


@router.get("/users/{user_id}/panel")
def user_panel_payload(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="user not found")
    assignments = db.scalars(select(CampaignAssignment).where(CampaignAssignment.user_id == user_id)).all()
    campaign_ids = sorted({a.campaign_id for a in assignments if a.campaign_id})
    campaigns = db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all() if campaign_ids else []
    weekly_rows = db.scalars(
        select(CapacityLedger).where(CapacityLedger.user_id == user_id).order_by(CapacityLedger.week_start.desc())
    ).all()
    return {
        "id": user.id,
        "name": user.full_name,
        "team": user.primary_team.value,
        "editorial_subteam": (
            user.editorial_subteam.value if getattr(user, "editorial_subteam", None) and hasattr(user.editorial_subteam, "value")
            else (str(user.editorial_subteam) if getattr(user, "editorial_subteam", None) else None)
        ),
        "capacity": {
            "rows": [
                {
                    "week_start": r.week_start.isoformat(),
                    "capacity_hours": float(r.capacity_hours),
                    "forecast_planned_hours": float(r.forecast_planned_hours),
                    "active_planned_hours": float(r.active_planned_hours),
                    "utilization_pct": round((float(r.forecast_planned_hours) / float(r.capacity_hours) * 100.0), 2) if float(r.capacity_hours) > 0 else 0.0,
                }
                for r in weekly_rows[:13]
            ],
        },
        "campaigns_participated": [
            {"id": c.display_id, "title": c.title}
            for c in campaigns
        ],
    }


@router.get("/milestones")
def list_milestones(db: Session = Depends(get_db)):
    items = db.scalars(select(Milestone).order_by(Milestone.created_at.asc())).all()
    milestone_service = MilestoneService(db)
    for item in items:
        milestone_service.refresh_sla(item)
    db.flush()
    return {
        "items": [
            {
                "id": m.display_id,
                "campaign_id": m.campaign_id,
                "stage_id": m.stage_id,
                "owner_user_id": m.owner_user_id,
                "name": m.name,
                "due_date": m.due_date.isoformat() if m.due_date else None,
                "completion_date": m.completion_date.isoformat() if m.completion_date else None,
                "sla_health": m.sla_health.value if hasattr(m.sla_health, "value") else m.sla_health,
                "sla_health_manual_override": bool(m.sla_health_manual_override),
                "baseline_date": m.baseline_date.isoformat() if m.baseline_date else None,
                "current_target_date": m.current_target_date.isoformat() if m.current_target_date else None,
                "achieved_at": m.achieved_at.isoformat() if m.achieved_at else None,
            }
            for m in items
        ]
    }


@router.patch("/milestones/{milestone_id}")
def update_milestone(milestone_id: str, payload: MilestoneUpdateIn, db: Session = Depends(get_db)):
    milestone = _resolve_by_identifier(db, Milestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="milestone not found")
    actor = AuthzService(db).actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_campaign_dates",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient permissions to manage milestone")
    if payload.owner_user_id is not None:
        if payload.owner_user_id:
            owner = db.get(User, payload.owner_user_id)
            if not owner:
                raise HTTPException(status_code=400, detail="owner user not found")
        milestone.owner_user_id = payload.owner_user_id or None
    if payload.due_date_iso is not None and payload.due_date_iso.strip():
        due = date.fromisoformat(payload.due_date_iso.strip())
        due = build_default_working_calendar().next_working_day_on_or_after(due)
        milestone.due_date = due
        milestone.current_target_date = due
        campaign = db.get(Campaign, milestone.campaign_id) if milestone.campaign_id else None
        if campaign and campaign.planned_start_date:
            milestone.offset_days_from_campaign_start = (due - campaign.planned_start_date).days
    MilestoneService(db).refresh_sla(milestone)
    db.commit()
    return {
        "id": milestone.display_id,
        "owner_user_id": milestone.owner_user_id,
        "due_date": milestone.due_date.isoformat() if milestone.due_date else None,
        "completion_date": milestone.completion_date.isoformat() if milestone.completion_date else None,
        "sla_health": milestone.sla_health.value if hasattr(milestone.sla_health, "value") else milestone.sla_health,
        "sla_health_manual_override": bool(milestone.sla_health_manual_override),
    }


@router.patch("/milestones/{milestone_id}/completion")
def update_milestone_completion(milestone_id: str, payload: MilestoneCompletionUpdateIn, db: Session = Depends(get_db)):
    milestone = _resolve_by_identifier(db, Milestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="milestone not found")
    actor = AuthzService(db).actor(payload.actor_user_id)
    if not _actor_has_control_permission(
        db,
        actor,
        "manage_step",
        fallback_allowed_roles={RoleName.CM, RoleName.HEAD_OPS, RoleName.ADMIN},
    ):
        raise HTTPException(status_code=403, detail="insufficient permissions to complete milestone")
    completion = date.fromisoformat(payload.completion_date_iso) if payload.completion_date_iso else None
    MilestoneService(db).set_completion_date(milestone, completion)
    db.commit()
    return {
        "id": milestone.display_id,
        "completion_date": milestone.completion_date.isoformat() if milestone.completion_date else None,
        "sla_health": milestone.sla_health.value if hasattr(milestone.sla_health, "value") else milestone.sla_health,
        "sla_health_manual_override": bool(milestone.sla_health_manual_override),
    }


@router.patch("/milestones/{milestone_id}/sla")
def override_milestone_sla(milestone_id: str, payload: MilestoneSlaOverrideIn, db: Session = Depends(get_db)):
    milestone = _resolve_by_identifier(db, Milestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="milestone not found")
    service = MilestoneService(db)
    if payload.clear_override:
        service.clear_sla_override(milestone)
    else:
        try:
            target = MilestoneSlaHealth(str(payload.sla_health).strip().lower())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid sla_health") from exc
        service.override_sla_health(milestone, actor_user_id=payload.actor_user_id, sla_health=target)
    db.commit()
    return {
        "id": milestone.display_id,
        "sla_health": milestone.sla_health.value if hasattr(milestone.sla_health, "value") else milestone.sla_health,
        "sla_health_manual_override": bool(milestone.sla_health_manual_override),
        "sla_health_overridden_by_user_id": milestone.sla_health_overridden_by_user_id,
    }


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    deals = db.scalars(select(Deal)).all()
    campaigns = db.scalars(select(Campaign)).all()
    deliverables = db.scalars(select(Deliverable)).all()
    steps = db.scalars(select(WorkflowStep)).all()

    at_risk_steps = [
        s
        for s in steps
        if s.current_due is not None and s.actual_done is None
    ]

    awaiting_client_review = [
        d for d in deliverables if d.status == DeliverableStatus.AWAITING_CLIENT_REVIEW
    ]
    waiting_publish = [
        d for d in deliverables if d.status == DeliverableStatus.READY_TO_PUBLISH
    ]
    open_system_risks = db.scalars(select(SystemRisk).where(SystemRisk.is_open.is_(True))).all()
    open_manual_risks = db.scalars(select(ManualRisk).where(ManualRisk.is_open.is_(True))).all()
    over_capacity_rows = db.scalars(
        select(CapacityLedger).where(CapacityLedger.planned_hours > CapacityLedger.capacity_hours)
    ).all()
    open_escalations = db.scalars(select(Escalation).where(Escalation.resolved_at.is_(None))).all()

    return {
        "deals_total": len(deals),
        "deals_readiness_passed": len([d for d in deals if d.readiness_passed]),
        "campaigns_total": len(campaigns),
        "deliverables_total": len(deliverables),
        "workflow_steps_open": len([s for s in steps if s.actual_done is None]),
        "workflow_steps_due_tracked": len(at_risk_steps),
        "awaiting_client_review": len(awaiting_client_review),
        "ready_to_publish": len(waiting_publish),
        "open_system_risks": len(open_system_risks),
        "open_manual_risks": len(open_manual_risks),
        "over_capacity_rows": len(over_capacity_rows),
        "open_escalations": len(open_escalations),
    }
