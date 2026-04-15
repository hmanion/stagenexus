from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import and_, func, or_, select

from app.db.session import SessionLocal
from app.models.domain import (
    ActivityLog,
    Campaign,
    CampaignAssignment,
    CampaignType,
    Deal,
    DealProductLine,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Milestone,
    ProductModule,
    Publication,
    PublicationName,
    Review,
    ReviewWindow,
    ReviewWindowStatus,
    ReviewWindowType,
    Role,
    RoleName,
    TemplateVersion,
    User,
    UserRoleAssignment,
    WorkflowStep,
    WorkflowStepKind,
    WorkflowStepDependency,
    Sprint,
)
from app.seeds.bootstrap_seed import seed_bootstrap
from app.services.campaign_generation_service import CampaignGenerationService
from app.services.id_service import PublicIdService
from app.services.ops_job_service import OpsJobService


LEGACY_MILESTONE_MAP = {
    "writing_complete": "writing",
    "internal_review_complete": "internal_review",
    "client_review_complete": "client_review",
    "promoting_complete": "promoting",
}


ANCHOR_DELIVERABLE_ORDER = [
    DeliverableType.ARTICLE,
    DeliverableType.VIDEO,
    DeliverableType.LANDING_PAGE,
    DeliverableType.EMAIL,
    DeliverableType.REPORT,
    DeliverableType.ENGAGEMENT_LIST,
    DeliverableType.CLIP,
    DeliverableType.SHORT,
    DeliverableType.DISPLAY_ASSET,
]


@dataclass
class BackfillStats:
    campaigns_template_updated: int = 0
    campaigns_cc_assigned: int = 0
    milestones_updated: int = 0
    milestones_created: int = 0
    milestones_deleted: int = 0
    legacy_deliverables_removed: int = 0
    steps_moved_to_anchor: int = 0
    lead_total_deliverables_created: int = 0
    legacy_review_steps_removed: int = 0


def _default_cc_user_id(db) -> str | None:
    cc_role = db.scalar(select(Role).where(Role.name == RoleName.CC))
    if cc_role:
        assigned = db.scalar(select(UserRoleAssignment).where(UserRoleAssignment.role_id == cc_role.id))
        if assigned:
            return assigned.user_id
    user = db.scalar(select(User).where(User.email.like("cc@%")))
    return user.id if user else None


def _latest_templates_by_name(db) -> dict[str, TemplateVersion]:
    rows = db.scalars(select(TemplateVersion).order_by(TemplateVersion.name.asc(), TemplateVersion.version.desc())).all()
    latest: dict[str, TemplateVersion] = {}
    for row in rows:
        latest.setdefault(row.name, row)
    return latest


def _ensure_cc_assignments(db, campaigns: list[Campaign], stats: BackfillStats) -> None:
    default_cc = _default_cc_user_id(db)
    if not default_cc:
        return

    for campaign in campaigns:
        has_cc = db.scalar(
            select(CampaignAssignment).where(
                CampaignAssignment.campaign_id == campaign.id,
                CampaignAssignment.role_name == RoleName.CC,
            )
        )
        if has_cc:
            continue
        db.add(CampaignAssignment(campaign_id=campaign.id, role_name=RoleName.CC, user_id=default_cc))
        stats.campaigns_cc_assigned += 1


def _update_template_pins(db, campaigns: list[Campaign], latest_templates: dict[str, TemplateVersion], stats: BackfillStats) -> None:
    for campaign in campaigns:
        template_name = campaign.campaign_type.value
        latest = latest_templates.get(template_name)
        if not latest:
            continue
        if campaign.template_version_id != latest.id:
            campaign.template_version_id = latest.id
            stats.campaigns_template_updated += 1


def _upsert_tdtimeline_milestones(db, generator: CampaignGenerationService, sprint_id: str, sprint_start: date, public_ids: PublicIdService, stats: BackfillStats) -> None:
    expected = generator._tdtimeline_default_milestones(sprint_start)  # noqa: SLF001
    expected_map = {name: dt for name, dt in expected}

    rows = db.scalars(select(Milestone).where(Milestone.sprint_id == sprint_id)).all()
    by_name: dict[str, list[Milestone]] = defaultdict(list)
    for m in rows:
        by_name[m.name].append(m)

    keep_ids: set[str] = set()
    for target_name, target_date in expected_map.items():
        candidates = by_name.get(target_name, [])
        for legacy, mapped in LEGACY_MILESTONE_MAP.items():
            if mapped == target_name:
                candidates += by_name.get(legacy, [])
        row = candidates[0] if candidates else None
        if row:
            if row.name != target_name:
                row.name = target_name
            row.baseline_date = target_date
            row.current_target_date = target_date
            keep_ids.add(row.id)
            stats.milestones_updated += 1
            continue
        db.add(
            Milestone(
                display_id=public_ids.next_id(Milestone, "MS"),
                sprint_id=sprint_id,
                name=target_name,
                baseline_date=target_date,
                current_target_date=target_date,
            )
        )
        stats.milestones_created += 1

    for row in rows:
        if row.id not in keep_ids and row.name not in expected_map and row.name not in LEGACY_MILESTONE_MAP:
            db.delete(row)
            stats.milestones_deleted += 1
        elif row.id not in keep_ids and row.name in LEGACY_MILESTONE_MAP:
            db.delete(row)
            stats.milestones_deleted += 1


def _anchor_deliverable(deliverables: list[Deliverable]) -> Deliverable | None:
    type_map = {d.deliverable_type: d for d in deliverables}
    for dtype in ANCHOR_DELIVERABLE_ORDER:
        if dtype in type_map:
            return type_map[dtype]
    return deliverables[0] if deliverables else None


def _migrate_legacy_call_deliverables(db, sprint_id: str, public_ids: PublicIdService, stats: BackfillStats) -> None:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        return
    canonical_briefing = "Kick-off call" if int(sprint.sprint_number or 1) == 1 else "Sprint briefing call"
    canonical = [
        ("background research", "Background research", WorkflowStepKind.TASK, RoleName.CC, 2.0),
        ("briefing_call", canonical_briefing, WorkflowStepKind.CALL, RoleName.CM, 1.0),
        ("content_plan", "Create content plan", WorkflowStepKind.TASK, RoleName.CC, 2.0),
        ("interview_call", "Interview call", WorkflowStepKind.CALL, RoleName.CC, 1.5),
    ]
    alias_map = {
        "background research": {"background research", "cc prep for ko/planning"},
        canonical_briefing.lower(): {"kick-off call", "run kick-off", "sprint briefing call", "run kickoff", "run kick off", "briefing"},
        "create content plan": {"create content plan"},
        "interview call": {"interview call", "run interview", "book interview"},
    }

    deliverables = db.scalars(select(Deliverable).where(Deliverable.sprint_id == sprint_id)).all()
    deliverable_ids = [d.id for d in deliverables]
    legacy = [d for d in deliverables if d.deliverable_type in {DeliverableType.KICKOFF_CALL, DeliverableType.INTERVIEW_CALL}]
    step_filters = [WorkflowStep.sprint_id == sprint_id]
    if deliverable_ids:
        step_filters.append(WorkflowStep.deliverable_id.in_(deliverable_ids))
    steps = db.scalars(
        select(WorkflowStep).where(or_(*step_filters)).order_by(WorkflowStep.created_at.asc())
    ).all()
    remaining = list(steps)
    kept_ids: list[str] = []

    for _, canonical_name, step_kind, owner_role, planned_hours in canonical:
        aliases = alias_map.get(canonical_name.lower(), {canonical_name.lower()})
        matches = [st for st in remaining if str(st.name or "").strip().lower() in aliases]
        if matches:
            keep = matches[0]
            keep.name = canonical_name
            keep.step_kind = step_kind
            keep.owner_role = owner_role
            keep.sprint_id = sprint_id
            keep.deliverable_id = None
            if (keep.planned_hours or 0) <= 0:
                keep.planned_hours = planned_hours
                keep.planned_hours_baseline = planned_hours
            kept_ids.append(keep.id)
            for dup in matches[1:]:
                remaining.remove(dup)
                db.query(WorkflowStepDependency).filter(
                    or_(
                        WorkflowStepDependency.predecessor_step_id == dup.id,
                        WorkflowStepDependency.successor_step_id == dup.id,
                    )
                ).delete(synchronize_session=False)
                db.delete(dup)
            remaining.remove(keep)
            continue

        new_step = WorkflowStep(
            display_id=public_ids.next_id(WorkflowStep, "STEP"),
            sprint_id=sprint_id,
            deliverable_id=None,
            name=canonical_name,
            step_kind=step_kind,
            owner_role=owner_role,
            planned_hours=planned_hours,
            planned_hours_baseline=planned_hours,
            baseline_start=sprint.current_start or sprint.baseline_start,
            baseline_due=sprint.current_start or sprint.baseline_start,
            current_start=sprint.current_start or sprint.baseline_start,
            current_due=sprint.current_start or sprint.baseline_start,
            stuck_threshold_days=2,
        )
        db.add(new_step)
        db.flush()
        kept_ids.append(new_step.id)

    if kept_ids:
        db.query(WorkflowStepDependency).filter(
            or_(
                WorkflowStepDependency.predecessor_step_id.in_(kept_ids),
                WorkflowStepDependency.successor_step_id.in_(kept_ids),
            )
        ).delete(synchronize_session=False)
        for i in range(1, len(kept_ids)):
            db.add(
                WorkflowStepDependency(
                    display_id=public_ids.next_id(WorkflowStepDependency, "DEP"),
                    predecessor_step_id=kept_ids[i - 1],
                    successor_step_id=kept_ids[i],
                    dependency_type="finish_to_start",
                )
            )

    for d in legacy:
        legacy_steps = db.scalars(select(WorkflowStep).where(WorkflowStep.deliverable_id == d.id)).all()
        for st in legacy_steps:
            if st.id in kept_ids:
                continue
            db.query(WorkflowStepDependency).filter(
                or_(
                    WorkflowStepDependency.predecessor_step_id == st.id,
                    WorkflowStepDependency.successor_step_id == st.id,
                )
            ).delete(synchronize_session=False)
            db.delete(st)
        db.query(Review).filter(Review.deliverable_id == d.id).delete(synchronize_session=False)
        db.query(ActivityLog).filter(
            and_(ActivityLog.entity_type == "deliverable", ActivityLog.entity_id == d.id)
        ).delete(synchronize_session=False)
        db.delete(d)
        stats.legacy_deliverables_removed += 1


def _enforce_cc_owner_for_required_steps(db, stats: BackfillStats) -> None:
    forced_cc_names = {
        "create content plan",
        "interview call",
        "run interview",
        "video brief for design",
        "production",
    }
    cc_role = db.scalar(select(Role).where(Role.name == RoleName.CC))
    if not cc_role:
        return

    cc_users_by_campaign: dict[str, str] = {
        row.campaign_id: row.user_id
        for row in db.scalars(
            select(CampaignAssignment).where(CampaignAssignment.role_name == RoleName.CC)
        ).all()
    }
    deliverable_to_sprint = {d.id: d.sprint_id for d in db.scalars(select(Deliverable)).all()}
    sprint_to_campaign = {s.id: s.campaign_id for s in db.scalars(select(Sprint)).all()}

    rows = db.scalars(select(WorkflowStep)).all()
    changed = 0
    for step in rows:
        step_name = str(step.name or "").strip().lower()
        if step_name not in forced_cc_names:
            continue
        if step.owner_role != RoleName.CC:
            step.owner_role = RoleName.CC
            changed += 1

        sprint_id = step.sprint_id or deliverable_to_sprint.get(step.deliverable_id)
        campaign_id = sprint_to_campaign.get(sprint_id) if sprint_id else None
        cc_user_id = cc_users_by_campaign.get(campaign_id) if campaign_id else None
        if cc_user_id and step.actual_done is None and step.waiting_on_type is None and step.next_owner_user_id != cc_user_id:
            step.next_owner_user_id = cc_user_id
            changed += 1

    stats.steps_moved_to_anchor += changed


def _migrate_to_campaign_direct_model(db, stats: BackfillStats) -> None:
    sprints = db.scalars(select(Sprint).order_by(Sprint.created_at.asc())).all()
    if not sprints:
        return

    by_campaign: dict[str, list[Sprint]] = defaultdict(list)
    for s in sprints:
        by_campaign[s.campaign_id].append(s)
    for rows in by_campaign.values():
        rows.sort(key=lambda x: (int(x.sprint_number or 0), x.created_at))

    campaigns = {c.id: c for c in db.scalars(select(Campaign)).all()}
    for campaign_id, rows in by_campaign.items():
        campaign = campaigns.get(campaign_id)
        if not campaign:
            continue
        if campaign.campaign_type == CampaignType.DEMAND:
            if rows:
                first = rows[0]
                campaign.is_demand_sprint = True
                campaign.demand_sprint_number = int(first.sprint_number or 1)
                campaign.demand_track = campaign.demand_track or "create_reach"

    deliverables = db.scalars(select(Deliverable)).all()
    for d in deliverables:
        if d.campaign_id:
            continue
        if d.sprint_id:
            sprint = next((s for s in sprints if s.id == d.sprint_id), None)
            if sprint:
                d.campaign_id = sprint.campaign_id

    milestones = db.scalars(select(Milestone)).all()
    for m in milestones:
        if not m.campaign_id and m.sprint_id:
            sprint = next((s for s in sprints if s.id == m.sprint_id), None)
            if sprint:
                m.campaign_id = sprint.campaign_id

    modules = db.scalars(select(ProductModule)).all()
    for pm in modules:
        if not pm.campaign_id and pm.sprint_id:
            sprint = next((s for s in sprints if s.id == pm.sprint_id), None)
            if sprint:
                pm.campaign_id = sprint.campaign_id

    steps = db.scalars(select(WorkflowStep)).all()
    deliverable_map = {d.id: d for d in deliverables}
    for st in steps:
        if not st.campaign_id and st.sprint_id:
            sprint = next((s for s in sprints if s.id == st.sprint_id), None)
            if sprint:
                st.campaign_id = sprint.campaign_id
        # Keep legacy sprint links for compatibility while campaign_id becomes source-of-truth.


def _migrate_review_windows_and_counters(db, public_ids: PublicIdService, stats: BackfillStats) -> None:
    deliverables = db.scalars(select(Deliverable)).all()
    for d in deliverables:
        internal_count = db.scalar(
            select(func.count()).select_from(Review).where(
                Review.deliverable_id == d.id,
                Review.review_type == "internal",
            )
        ) or 0
        client_count = db.scalar(
            select(func.count()).select_from(Review).where(
                Review.deliverable_id == d.id,
                Review.review_type == "client",
            )
        ) or 0
        amend_count = db.scalar(
            select(func.count()).select_from(Review).where(
                Review.deliverable_id == d.id,
                Review.review_type == "client",
                Review.status == "changes_requested",
            )
        ) or 0
        d.internal_review_rounds = max(int(d.internal_review_rounds or 0), int(internal_count))
        d.client_review_rounds = max(int(d.client_review_rounds or 0), int(client_count))
        d.amend_rounds = max(int(d.amend_rounds or 0), int(amend_count))

        legacy_steps = db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.deliverable_id == d.id,
                func.lower(WorkflowStep.name).in_(["internal review", "client review", "final approval", "amends reserve"]),
            )
        ).all()
        if legacy_steps:
            step_ids = [s.id for s in legacy_steps]
            db.query(WorkflowStepDependency).filter(
                or_(
                    WorkflowStepDependency.predecessor_step_id.in_(step_ids),
                    WorkflowStepDependency.successor_step_id.in_(step_ids),
                )
            ).delete(synchronize_session=False)
            for s in legacy_steps:
                db.delete(s)
                stats.legacy_review_steps_removed += 1

        has_open_window = db.scalar(
            select(ReviewWindow).where(
                ReviewWindow.deliverable_id == d.id,
                ReviewWindow.status == ReviewWindowStatus.OPEN,
            )
        )
        if has_open_window:
            continue
        now = datetime.utcnow()
        if d.status == DeliverableStatus.AWAITING_INTERNAL_REVIEW:
            db.add(
                ReviewWindow(
                    display_id=public_ids.next_id(ReviewWindow, "RWIN"),
                    deliverable_id=d.id,
                    window_type=ReviewWindowType.INTERNAL_REVIEW,
                    window_start=now.date(),
                    window_due=now.date(),
                    status=ReviewWindowStatus.OPEN,
                    round_number=max(int(d.internal_review_rounds), 1),
                )
            )
        elif d.status == DeliverableStatus.AWAITING_CLIENT_REVIEW:
            db.add(
                ReviewWindow(
                    display_id=public_ids.next_id(ReviewWindow, "RWIN"),
                    deliverable_id=d.id,
                    window_type=ReviewWindowType.CLIENT_REVIEW,
                    window_start=now.date(),
                    window_due=now.date(),
                    status=ReviewWindowStatus.OPEN,
                    round_number=max(int(d.client_review_rounds), 1),
                )
            )
        elif d.status == DeliverableStatus.CLIENT_CHANGES_REQUESTED:
            db.add(
                ReviewWindow(
                    display_id=public_ids.next_id(ReviewWindow, "RWIN"),
                    deliverable_id=d.id,
                    window_type=ReviewWindowType.AMENDS,
                    window_start=now.date(),
                    window_due=now.date(),
                    status=ReviewWindowStatus.OPEN,
                    round_number=max(int(d.amend_rounds), 1),
                )
            )


def run_backfill() -> BackfillStats:
    stats = BackfillStats()
    with SessionLocal() as db:
        # Ensure current template versions/settings exist.
        seed_bootstrap(db)
        generator = CampaignGenerationService(db)
        public_ids = PublicIdService(db)

        campaigns = db.scalars(select(Campaign)).all()
        latest_templates = _latest_templates_by_name(db)
        _update_template_pins(db, campaigns, latest_templates, stats)
        _ensure_cc_assignments(db, campaigns, stats)

        sprints = db.scalars(select(Sprint)).all()
        for sprint in sprints:
            start = sprint.current_start or sprint.baseline_start or date.today()
            _upsert_tdtimeline_milestones(db, generator, sprint.id, start, public_ids, stats)
            _migrate_legacy_call_deliverables(db, sprint.id, public_ids, stats)

        _enforce_cc_owner_for_required_steps(db, stats)
        _ensure_response_lead_total_deliverables(db, public_ids, stats)
        _migrate_review_windows_and_counters(db, public_ids, stats)
        _migrate_to_campaign_direct_model(db, stats)

        summary = OpsJobService(db).run_all()
        db.commit()
        print(
            "ops_job:",
            {
                "capacity_rows_upserted": summary.capacity_rows_upserted,
                "over_capacity_rows": summary.over_capacity_rows,
                "system_risks_opened_or_updated": summary.system_risks_opened_or_updated,
                "escalations_opened": summary.escalations_opened,
            },
        )
    return stats


def _response_lead_volume_for_campaign(db, campaign: Campaign) -> int | None:
    lines = db.scalars(
        select(DealProductLine).where(
            DealProductLine.deal_id == campaign.deal_id,
            DealProductLine.product_type == campaign.campaign_type,
            DealProductLine.tier == campaign.tier,
        )
    ).all()
    if not lines:
        lines = db.scalars(
            select(DealProductLine).where(
                DealProductLine.deal_id == campaign.deal_id,
                DealProductLine.product_type == campaign.campaign_type,
            )
        ).all()
    for line in lines:
        raw = (line.options_json or {}).get("lead_volume")
        if raw is None:
            continue
        try:
            val = int(raw)
            if val > 0:
                return val
        except (TypeError, ValueError):
            continue
    return None


def _ensure_response_lead_total_deliverables(db, public_ids: PublicIdService, stats: BackfillStats) -> None:
    campaigns = db.scalars(select(Campaign).where(Campaign.campaign_type == CampaignType.RESPONSE)).all()
    for campaign in campaigns:
        sprints = db.scalars(
            select(Sprint).where(Sprint.campaign_id == campaign.id).order_by(Sprint.sprint_number.asc())
        ).all()
        if not sprints:
            continue
        target_sprint = sprints[-1]
        existing = db.scalar(
            select(Deliverable).where(
                Deliverable.sprint_id == target_sprint.id,
                Deliverable.deliverable_type == DeliverableType.LEAD_TOTAL,
            )
        )
        deal = db.get(Deal, campaign.deal_id)
        due_date = deal.sow_end_date if deal and deal.sow_end_date else None
        if existing:
            existing.baseline_due = due_date
            existing.current_due = due_date
            continue

        publication_id = None
        any_deliverable = db.scalar(select(Deliverable).where(Deliverable.sprint_id == target_sprint.id))
        if any_deliverable:
            publication_id = any_deliverable.publication_id
        else:
            publication = db.scalar(select(Publication).where(Publication.name == PublicationName.UC_TODAY))
            publication_id = publication.id if publication else None
        if not publication_id:
            continue

        lead_volume = _response_lead_volume_for_campaign(db, campaign)
        title = f"Total leads ({lead_volume}) due by campaign end" if lead_volume else "Total leads due by campaign end"
        deliverable = Deliverable(
            display_id=public_ids.next_id(Deliverable, "DEL"),
            sprint_id=target_sprint.id,
            publication_id=publication_id,
            deliverable_type=DeliverableType.LEAD_TOTAL,
            title=title,
            status=DeliverableStatus.PLANNED,
            baseline_due=due_date,
            current_due=due_date,
        )
        db.add(deliverable)
        db.flush()
        db.add(
            WorkflowStep(
                display_id=public_ids.next_id(WorkflowStep, "STEP"),
                deliverable_id=deliverable.id,
                name="Confirm final lead total",
                owner_role=RoleName.CM,
                planned_hours=0.5,
                planned_hours_baseline=0.5,
                baseline_start=target_sprint.current_start or target_sprint.baseline_start,
                baseline_due=due_date or target_sprint.current_start or target_sprint.baseline_start,
                current_start=target_sprint.current_start or target_sprint.baseline_start,
                current_due=due_date or target_sprint.current_start or target_sprint.baseline_start,
                stuck_threshold_days=3,
            )
        )
        stats.lead_total_deliverables_created += 1


def main() -> None:
    stats = run_backfill()
    print("backfill_stats:", stats)


if __name__ == "__main__":
    main()
