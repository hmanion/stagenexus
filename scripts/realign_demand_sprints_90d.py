from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.domain import (
    ActivityLog,
    Campaign,
    CampaignType,
    Deal,
    Deliverable,
    Milestone,
    ReviewWindow,
    WorkflowStep,
)
from app.services.calendar_service import build_calendar
from app.services.id_service import PublicIdService
from app.services.ops_job_service import OpsJobService


@dataclass
class ShiftStats:
    campaigns_shifted: int = 0
    milestones_shifted: int = 0
    deliverables_shifted: int = 0
    steps_shifted: int = 0
    review_windows_shifted: int = 0


def _product_code_from_campaign_id(display_id: str | None) -> str:
    # Expected: AAAA-YY-CCCC-NN
    if not display_id:
        return ""
    parts = str(display_id).split("-")
    return parts[2] if len(parts) >= 4 else ""


def _kickoff_anchor(campaign_id: str, milestones_by_campaign: dict[str, list[Milestone]]) -> date | None:
    milestones = milestones_by_campaign.get(campaign_id) or []
    kickoff = next((m for m in milestones if str(m.name).strip().lower() == "kickoff"), None)
    if kickoff:
        return kickoff.current_target_date or kickoff.baseline_date
    if milestones:
        first = sorted(
            [m for m in milestones if (m.current_target_date or m.baseline_date)],
            key=lambda m: m.current_target_date or m.baseline_date,
        )
        if first:
            return first[0].current_target_date or first[0].baseline_date
    return None


def _shift_working(d: date | None, delta_days: int, calendar) -> date | None:
    if d is None:
        return None
    shifted = d + timedelta(days=delta_days)
    return calendar.next_working_day_on_or_after(shifted)


def _realign() -> ShiftStats:
    stats = ShiftStats()
    calendar = build_calendar()
    with SessionLocal() as db:
        public_ids = PublicIdService(db)
        demand_sprint_campaigns = db.scalars(
            select(Campaign).where(
                Campaign.campaign_type == CampaignType.DEMAND,
                Campaign.is_demand_sprint.is_(True),
                Campaign.demand_sprint_number.is_not(None),
            )
        ).all()
        if not demand_sprint_campaigns:
            print("No Demand sprint campaigns found.")
            return stats

        campaign_ids = [c.id for c in demand_sprint_campaigns]
        milestones = db.scalars(select(Milestone).where(Milestone.campaign_id.in_(campaign_ids))).all()
        milestones_by_campaign: dict[str, list[Milestone]] = defaultdict(list)
        for m in milestones:
            milestones_by_campaign[m.campaign_id].append(m)

        grouped: dict[tuple[str, str], list[Campaign]] = defaultdict(list)
        for c in demand_sprint_campaigns:
            grouped[(c.deal_id, _product_code_from_campaign_id(c.display_id))].append(c)

        for (deal_id, product_code), campaigns in grouped.items():
            deal = db.get(Deal, deal_id)
            campaigns_sorted = sorted(campaigns, key=lambda c: int(c.demand_sprint_number or 999))
            if not campaigns_sorted:
                continue

            sprint1 = campaigns_sorted[0]
            sprint1_anchor = _kickoff_anchor(sprint1.id, milestones_by_campaign) or deal.sow_start_date or date.today()
            sprint1_anchor = calendar.next_working_day_on_or_after(sprint1_anchor)

            for campaign in campaigns_sorted:
                sprint_num = int(campaign.demand_sprint_number or 1)
                target_anchor = calendar.next_working_day_on_or_after(
                    sprint1_anchor + timedelta(days=(sprint_num - 1) * 90)
                )
                current_anchor = _kickoff_anchor(campaign.id, milestones_by_campaign) or deal.sow_start_date or target_anchor
                delta_days = (target_anchor - current_anchor).days
                if delta_days == 0:
                    continue

                # Shift milestones (except achieved ones).
                for m in milestones_by_campaign.get(campaign.id, []):
                    if m.achieved_at:
                        continue
                    m.baseline_date = _shift_working(m.baseline_date, delta_days, calendar)
                    m.current_target_date = _shift_working(m.current_target_date, delta_days, calendar)
                    stats.milestones_shifted += 1

                deliverables = db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
                deliverable_ids = [d.id for d in deliverables]
                for d in deliverables:
                    if d.actual_done:
                        continue
                    d.baseline_due = _shift_working(d.baseline_due, delta_days, calendar)
                    d.current_due = _shift_working(d.current_due, delta_days, calendar)
                    stats.deliverables_shifted += 1

                steps = db.scalars(select(WorkflowStep).where(WorkflowStep.campaign_id == campaign.id)).all()
                for s in steps:
                    if s.actual_done:
                        continue
                    s.baseline_start = _shift_working(s.baseline_start, delta_days, calendar)
                    s.baseline_due = _shift_working(s.baseline_due, delta_days, calendar)
                    s.current_start = _shift_working(s.current_start, delta_days, calendar)
                    s.current_due = _shift_working(s.current_due, delta_days, calendar)
                    stats.steps_shifted += 1

                if deliverable_ids:
                    windows = db.scalars(select(ReviewWindow).where(ReviewWindow.deliverable_id.in_(deliverable_ids))).all()
                    for w in windows:
                        if w.completed_at:
                            continue
                        w.window_start = _shift_working(w.window_start, delta_days, calendar) or w.window_start
                        w.window_due = _shift_working(w.window_due, delta_days, calendar) or w.window_due
                        stats.review_windows_shifted += 1

                db.add(
                    ActivityLog(
                        display_id=public_ids.next_id(ActivityLog, "ACT"),
                        actor_user_id=None,
                        entity_type="campaign",
                        entity_id=campaign.id,
                        action="demand_sprint_reanchored_90_day",
                        meta_json={
                            "campaign_id": campaign.display_id,
                            "deal_id": deal.display_id if deal else None,
                            "product_code": product_code,
                            "sprint_number": sprint_num,
                            "old_anchor": current_anchor.isoformat() if current_anchor else None,
                            "new_anchor": target_anchor.isoformat(),
                            "delta_days": delta_days,
                        },
                    )
                )
                stats.campaigns_shifted += 1

        summary = OpsJobService(db).run_all()
        db.commit()

    print("Demand sprint realignment complete:")
    print(f"- campaigns_shifted: {stats.campaigns_shifted}")
    print(f"- milestones_shifted: {stats.milestones_shifted}")
    print(f"- deliverables_shifted: {stats.deliverables_shifted}")
    print(f"- steps_shifted: {stats.steps_shifted}")
    print(f"- review_windows_shifted: {stats.review_windows_shifted}")
    print(f"- capacity_rows_upserted: {summary.capacity_rows_upserted}")
    print(f"- system_risks_opened_or_updated: {summary.system_risks_opened_or_updated}")
    return stats


if __name__ == "__main__":
    _realign()
