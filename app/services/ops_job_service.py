from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Campaign,
    CampaignAssignment,
    CapacityLedger,
    Deal,
    Deliverable,
    DeliverableStatus,
    DeliverableType,
    Escalation,
    ReviewWindow,
    ReviewWindowStatus,
    ReviewWindowType,
    RiskSeverity,
    Role,
    RoleName,
    SystemRisk,
    UserRoleAssignment,
    WorkflowStep,
    WorkflowStepEffort,
)
from app.services.calendar_service import build_default_working_calendar
from app.services.capacity_service import CapacityService
from app.services.timeline_service import TimelineService
from app.services.id_service import PublicIdService
from app.services.risk_service import RiskService
from app.services.campaign_health_service import CampaignHealthService
from app.services.stage_integrity_service import StageIntegrityService


@dataclass
class OpsJobSummary:
    capacity_rows_upserted: int
    over_capacity_rows: int
    system_risks_opened_or_updated: int
    escalations_opened: int


class OpsJobService:
    def __init__(self, db: Session):
        self.db = db
        self.capacity = CapacityService(db)
        self.risk = RiskService()
        self.health = CampaignHealthService(db)
        self.stage_integrity = StageIntegrityService(db)
        self.public_ids = PublicIdService(db)
        self.calendar = build_default_working_calendar()
        self.timeline = TimelineService(self.calendar)

    def run_all(self) -> OpsJobSummary:
        self._reconcile_campaign_stages()
        self._backfill_missing_deliverable_due_dates()
        self._backfill_missing_step_owners()
        capacity_rows, over_capacity_rows, capacity_risks = self._run_capacity_ledger()
        risk_rows, risk_codes = self._run_step_risk_scan()
        review_risk_rows, review_risk_codes = self._run_deliverable_review_risk_scan()
        health_risk_rows, health_risk_codes = self._run_campaign_health_risk_scan()
        self.db.flush()

        total_risk_keys = capacity_risks.union(risk_codes).union(review_risk_codes).union(health_risk_codes)
        self._close_resolved_system_risks(total_risk_keys)
        self._close_resolved_escalations()

        escalations = self._ensure_escalations()
        return OpsJobSummary(
            capacity_rows_upserted=capacity_rows,
            over_capacity_rows=over_capacity_rows,
            system_risks_opened_or_updated=(len(capacity_risks) + len(risk_codes) + len(review_risk_codes) + len(health_risk_codes)),
            escalations_opened=escalations,
        )

    def _reconcile_campaign_stages(self) -> None:
        campaign_ids = list(self.db.scalars(select(Campaign.id)).all())
        for campaign_id in campaign_ids:
            self.stage_integrity.reconcile_campaign(campaign_id)

    def _backfill_missing_deliverable_due_dates(self) -> None:
        deliverables = self.db.scalars(
            select(Deliverable).where(
                (Deliverable.current_due.is_(None)) | (Deliverable.baseline_due.is_(None))
            )
        ).all()
        if not deliverables:
            return
        campaign_ids = sorted({d.campaign_id for d in deliverables if d.campaign_id})
        campaigns = {c.id: c for c in self.db.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids))).all()}
        deal_ids = sorted({c.deal_id for c in campaigns.values()})
        deals = {d.id: d for d in self.db.scalars(select(Deal).where(Deal.id.in_(deal_ids))).all()}

        for d in deliverables:
            campaign = campaigns.get(d.campaign_id) if d.campaign_id else None
            if not campaign:
                continue
            deal = deals.get(campaign.deal_id) if campaign else None
            anchor_start = campaign.planned_start_date or deal.sow_start_date if deal else campaign.created_at.date()
            due = self._default_deliverable_due(d.deliverable_type, anchor_start, deal.sow_end_date if deal else None)
            if d.baseline_due is None:
                d.baseline_due = due
            if d.current_due is None:
                d.current_due = due

    def _backfill_missing_step_owners(self) -> None:
        ownerless_steps = self.db.scalars(
            select(WorkflowStep).where(WorkflowStep.next_owner_user_id.is_(None))
        ).all()
        if not ownerless_steps:
            return
        step_ids = [s.id for s in ownerless_steps]
        effort_rows = (
            self.db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all()
            if step_ids
            else []
        )
        efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
        for effort in effort_rows:
            efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
        assignment_rows = self.db.scalars(select(CampaignAssignment)).all()
        assignment_map: dict[tuple[str, RoleName], str] = {
            (a.campaign_id, a.role_name): a.user_id for a in assignment_rows
        }
        for step in ownerless_steps:
            candidate = self._resolve_missing_owner_user_id(step, efforts_by_step.get(step.id, []), assignment_map)
            if candidate:
                step.next_owner_user_id = candidate

    def _resolve_missing_owner_user_id(
        self,
        step: WorkflowStep,
        effort_rows: list[WorkflowStepEffort],
        assignment_map: dict[tuple[str, RoleName], str],
    ) -> str | None:
        assigned_hours_by_user: dict[str, float] = {}
        for effort in effort_rows:
            user_id = effort.assigned_user_id
            hours = float(effort.hours or 0.0)
            if not user_id:
                continue
            assigned_hours_by_user[user_id] = assigned_hours_by_user.get(user_id, 0.0) + max(hours, 0.0)
        if len(assigned_hours_by_user) == 1:
            return next(iter(assigned_hours_by_user.keys()))
        if assigned_hours_by_user:
            max_hours = max(assigned_hours_by_user.values())
            winners = sorted([uid for uid, hours in assigned_hours_by_user.items() if hours == max_hours])
            if len(winners) == 1:
                return winners[0]
            campaign_id = self._campaign_id_for_step(step)
            if campaign_id:
                role_owner = assignment_map.get((campaign_id, step.owner_role))
                if role_owner and role_owner in winners:
                    return role_owner
            return winners[0]
        campaign_id = self._campaign_id_for_step(step)
        if campaign_id:
            fallback = assignment_map.get((campaign_id, step.owner_role))
            if fallback:
                return fallback
        return None

    def _run_capacity_ledger(self) -> tuple[int, int, set[tuple[str, str]]]:
        steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.actual_done.is_(None))).all()
        step_ids = [s.id for s in steps]
        efforts = self.db.scalars(select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id.in_(step_ids))).all() if step_ids else []
        efforts_by_step: dict[str, list[WorkflowStepEffort]] = {}
        for effort in efforts:
            efforts_by_step.setdefault(effort.workflow_step_id, []).append(effort)
        assignments = self.db.scalars(select(CampaignAssignment)).all()
        assignment_map: dict[tuple[str, RoleName], str] = {
            (a.campaign_id, a.role_name): a.user_id for a in assignments
        }

        grouped: dict[tuple[str, RoleName, date], dict] = defaultdict(
            lambda: {"active_planned_hours": 0.0, "forecast_planned_hours": 0.0, "campaign_ids": set()}
        )
        for step in steps:
            campaign_id = self._campaign_id_for_step(step)
            if not campaign_id:
                continue

            week_start = self._week_start(step.current_start or step.baseline_start or step.created_at.date())
            step_efforts = [e for e in efforts_by_step.get(step.id, []) if float(e.hours or 0.0) > 0.0]
            if not step_efforts:
                step_efforts = [
                    WorkflowStepEffort(
                        workflow_step_id=step.id,
                        role_name=step.owner_role,
                        hours=float(step.planned_hours or 0.0),
                        assigned_user_id=assignment_map.get((campaign_id, step.owner_role)) or step.next_owner_user_id,
                    )
                ]

            for effort in step_efforts:
                planned_hours = float(effort.hours or 0.0)
                if planned_hours <= 0:
                    continue
                role_name = effort.role_name
                forecast_owner_user_id = effort.assigned_user_id or assignment_map.get((campaign_id, role_name))

                if forecast_owner_user_id:
                    forecast_key = (forecast_owner_user_id, role_name, week_start)
                    grouped[forecast_key]["forecast_planned_hours"] += planned_hours
                    grouped[forecast_key]["campaign_ids"].add(campaign_id)

                if step.next_owner_user_id and forecast_owner_user_id and step.next_owner_user_id == forecast_owner_user_id:
                    active_key = (step.next_owner_user_id, role_name, week_start)
                    grouped[active_key]["active_planned_hours"] += planned_hours
                    grouped[active_key]["campaign_ids"].add(campaign_id)

        upserted = 0
        over_capacity = 0
        risk_keys: set[tuple[str, str]] = set()

        for (user_id, role_name, week_start), aggregate in grouped.items():
            forecast_hours = float(aggregate["forecast_planned_hours"])
            active_hours = float(aggregate["active_planned_hours"])
            evaluation = self.capacity.evaluate(role_name, forecast_hours)
            row = self.db.scalar(
                select(CapacityLedger).where(
                    CapacityLedger.user_id == user_id,
                    CapacityLedger.role_name == role_name,
                    CapacityLedger.week_start == week_start,
                )
            )
            if not row:
                row = CapacityLedger(
                    display_id=self.public_ids.next_id(CapacityLedger, "CAP"),
                    user_id=user_id,
                    role_name=role_name,
                    week_start=week_start,
                    capacity_hours=evaluation.capacity_hours,
                    planned_hours=evaluation.planned_hours,
                    active_planned_hours=active_hours,
                    forecast_planned_hours=forecast_hours,
                )
                self.db.add(row)
            else:
                row.capacity_hours = evaluation.capacity_hours
                row.planned_hours = evaluation.planned_hours
                row.active_planned_hours = active_hours
                row.forecast_planned_hours = forecast_hours

            upserted += 1

            if evaluation.is_over_capacity:
                over_capacity += 1
                if row.override_approved:
                    continue
                for campaign_id in aggregate["campaign_ids"]:
                    risk_code = f"capacity_overload:{user_id}:{role_name.value}:{week_start.isoformat()}"
                    self._upsert_system_risk(
                        campaign_id=campaign_id,
                        risk_code=risk_code,
                        severity=RiskSeverity.MEDIUM,
                        details=(
                            f"Forecast {forecast_hours:.1f}h (active {active_hours:.1f}h) exceeds "
                            f"{evaluation.capacity_hours:.1f}h for {role_name.value} in week starting {week_start.isoformat()}"
                        ),
                    )
                    risk_keys.add((campaign_id, risk_code))

        return upserted, over_capacity, risk_keys

    def _run_step_risk_scan(self) -> tuple[int, set[tuple[str, str]]]:
        rows = 0
        risk_keys: set[tuple[str, str]] = set()

        steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.actual_done.is_(None))).all()
        for step in steps:
            evaluated = self.risk.evaluate_step_risk(step)
            if not evaluated:
                continue

            risk_code_base, severity = evaluated
            campaign_id = self._campaign_id_for_step(step)
            if not campaign_id:
                continue

            risk_code = f"{risk_code_base}:{step.id}"
            self._upsert_system_risk(
                campaign_id=campaign_id,
                risk_code=risk_code,
                severity=severity,
                details=f"Workflow step '{step.name}' triggered {risk_code_base}",
            )
            rows += 1
            risk_keys.add((campaign_id, risk_code))

        return rows, risk_keys

    def _run_deliverable_review_risk_scan(self) -> tuple[int, set[tuple[str, str]]]:
        rows = 0
        risk_keys: set[tuple[str, str]] = set()
        today = date.today()
        windows = self.db.scalars(select(ReviewWindow).where(ReviewWindow.status == ReviewWindowStatus.OPEN)).all()
        deliverable_ids = sorted({w.deliverable_id for w in windows})
        deliverables = (
            {d.id: d for d in self.db.scalars(select(Deliverable).where(Deliverable.id.in_(deliverable_ids))).all()}
            if deliverable_ids
            else {}
        )

        for w in windows:
            d = deliverables.get(w.deliverable_id)
            if not d:
                continue
            campaign_id = self._campaign_id_for_deliverable(d.id)
            if not campaign_id:
                continue
            if not w.window_due or w.window_due >= today:
                continue
            overdue_days = max(self.timeline.working_days_between(w.window_due, today), 0)
            code = f"review_window_overdue:{w.id}"
            severity = RiskSeverity.MEDIUM
            if w.window_type == ReviewWindowType.CLIENT_REVIEW:
                severity = RiskSeverity.HIGH
            if overdue_days >= 5:
                severity = RiskSeverity.CRITICAL
            self._upsert_system_risk(
                campaign_id=campaign_id,
                risk_code=code,
                severity=severity,
                details=(
                    f"Deliverable '{d.title}' {w.window_type.value} round {w.round_number} window is overdue by "
                    f"{overdue_days} working day(s)"
                ),
            )
            rows += 1
            risk_keys.add((campaign_id, code))

        return rows, risk_keys

    def _run_campaign_health_risk_scan(self) -> tuple[int, set[tuple[str, str]]]:
        rows = 0
        risk_keys: set[tuple[str, str]] = set()
        campaigns = self.db.scalars(select(Campaign)).all()
        for campaign in campaigns:
            health = self.health.evaluate_campaign(campaign)
            for signal in self.health.health_risk_signals(health):
                severity = RiskSeverity.CRITICAL if signal["severity"] == "off_track" else RiskSeverity.MEDIUM
                step_id = signal.get("step_internal_id") or signal.get("step_id") or "campaign"
                code = f"health:{signal.get('dimension', 'checkpoint')}:{step_id}"
                self._upsert_system_risk(
                    campaign_id=campaign.id,
                    risk_code=code,
                    severity=severity,
                    details=f"{signal.get('reason', 'health risk')} (owner {signal.get('owner_role') or '-'})",
                )
                rows += 1
                risk_keys.add((campaign.id, code))
        return rows, risk_keys

    def _upsert_system_risk(self, campaign_id: str, risk_code: str, severity: RiskSeverity, details: str) -> None:
        risk = self.db.scalar(
            select(SystemRisk).where(
                SystemRisk.campaign_id == campaign_id,
                SystemRisk.risk_code == risk_code,
                SystemRisk.is_open.is_(True),
            )
        )
        if risk:
            risk.severity = severity
            risk.details = details
            return

        self.db.add(
            SystemRisk(
                display_id=self.public_ids.next_id(SystemRisk, "RSK"),
                campaign_id=campaign_id,
                risk_code=risk_code,
                severity=severity,
                details=details,
                is_open=True,
            )
        )

    def _close_resolved_system_risks(self, active_keys: set[tuple[str, str]]) -> None:
        open_risks = self.db.scalars(select(SystemRisk).where(SystemRisk.is_open.is_(True))).all()
        for r in open_risks:
            if (r.campaign_id, r.risk_code) not in active_keys:
                r.is_open = False

    def _close_resolved_escalations(self) -> None:
        open_escalations = self.db.scalars(
            select(Escalation).where(
                Escalation.risk_type == "system",
                Escalation.resolved_at.is_(None),
            )
        ).all()
        if not open_escalations:
            return
        risk_ids = [e.risk_id for e in open_escalations]
        risks = {
            r.id: r
            for r in self.db.scalars(select(SystemRisk).where(SystemRisk.id.in_(risk_ids))).all()
        }
        now = datetime.utcnow()
        for esc in open_escalations:
            risk = risks.get(esc.risk_id)
            if risk and not risk.is_open:
                esc.resolved_at = now

    def _ensure_escalations(self) -> int:
        created = 0
        head_ops_user_id = self._head_ops_user_id()
        if not head_ops_user_id:
            return created

        open_risks = self.db.scalars(select(SystemRisk).where(SystemRisk.is_open.is_(True))).all()
        escalatable = []
        for risk in open_risks:
            if risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}:
                escalatable.append(risk)
                continue
            if risk.risk_code.startswith("health:") and risk.severity == RiskSeverity.MEDIUM:
                age_days = self._working_days_since(risk.updated_at.date())
                if age_days >= 3:
                    escalatable.append(risk)
                    continue
            if (
                risk.risk_code.startswith("internal_review_stalled:")
                or risk.risk_code.startswith("client_review_stalled:")
                or risk.risk_code.startswith("review_window_overdue:")
            ):
                if self._is_review_stalled_2x_threshold(risk.risk_code):
                    escalatable.append(risk)

        for risk in escalatable:
            existing = self.db.scalar(
                select(Escalation).where(
                    Escalation.risk_type == "system",
                    Escalation.risk_id == risk.id,
                    Escalation.resolved_at.is_(None),
                )
            )
            if existing:
                continue

            self.db.add(
                Escalation(
                    display_id=self.public_ids.next_id(Escalation, "ESC"),
                    risk_type="system",
                    risk_id=risk.id,
                    escalated_to_user_id=head_ops_user_id,
                    reason=f"Auto-escalation for {risk.severity.value} risk {risk.risk_code}",
                )
            )
            created += 1

        return created

    def _is_review_stalled_2x_threshold(self, risk_code: str) -> bool:
        deliverable_id = (risk_code.split(":", 1)[1] if ":" in risk_code else "").strip()
        if not deliverable_id:
            return False
        deliverable = self.db.get(Deliverable, deliverable_id)
        if not deliverable:
            return False
        now = datetime.utcnow()
        if risk_code.startswith("internal_review_stalled:") and deliverable.awaiting_internal_review_since:
            age_days = max((now - deliverable.awaiting_internal_review_since).days, 0)
            threshold = max(int(deliverable.internal_review_stall_threshold_days), 1)
            return age_days >= (2 * threshold)
        if risk_code.startswith("client_review_stalled:") and deliverable.awaiting_client_review_since:
            age_days = max((now - deliverable.awaiting_client_review_since).days, 0)
            threshold = max(int(deliverable.client_review_stall_threshold_days), 1)
            return age_days >= (2 * threshold)
        if risk_code.startswith("review_window_overdue:"):
            window_id = (risk_code.split(":", 1)[1] if ":" in risk_code else "").strip()
            if not window_id:
                return False
            window = self.db.get(ReviewWindow, window_id)
            if not window or window.status != ReviewWindowStatus.OPEN:
                return False
            overdue_days = max(self.timeline.working_days_between(window.window_due, now.date()), 0)
            return overdue_days >= 4
        return False

    def _working_days_since(self, start_date: date) -> int:
        end_date = date.today()
        if start_date >= end_date:
            return 0
        return max(self.timeline.working_days_between(start_date, end_date), 0)

    def _head_ops_user_id(self) -> str | None:
        role = self.db.scalar(select(Role).where(Role.name == RoleName.HEAD_OPS))
        if not role:
            return None
        assignment = self.db.scalar(select(UserRoleAssignment).where(UserRoleAssignment.role_id == role.id))
        return assignment.user_id if assignment else None

    def _campaign_id_for_step(self, step: WorkflowStep) -> str | None:
        if step.campaign_id:
            return step.campaign_id
        linked_deliverable_id = step.linked_deliverable_id
        if not linked_deliverable_id:
            return None
        deliverable = self.db.get(Deliverable, linked_deliverable_id)
        if not deliverable:
            return None
        if deliverable.campaign_id:
            return deliverable.campaign_id
        return None

    def _campaign_id_for_deliverable(self, deliverable_id: str) -> str | None:
        deliverable = self.db.get(Deliverable, deliverable_id)
        if not deliverable:
            return None
        if deliverable.campaign_id:
            return deliverable.campaign_id
        return None

    @staticmethod
    def _week_start(d: date) -> date:
        # Week starts Monday.
        return d - timedelta(days=d.weekday())

    def _default_deliverable_due(self, deliverable_type: DeliverableType, sprint_start: date, sow_end_date: date | None) -> date:
        # Align due defaults with the timeline milestone cadence used in generation.
        defaults = (self.health.ops_defaults.get("timeline_defaults") or {})
        writing_days = int(defaults.get("writing_working_days", 8))
        internal_review_days = int(defaults.get("internal_review_working_days", 2))
        client_review_days = int(defaults.get("client_review_working_days", 5))
        publish_after_client_days = int(defaults.get("publish_after_client_review_working_days", 1))
        promotion_days = int(defaults.get("promotion_duration_calendar_days", 44))
        reporting_days = int(defaults.get("reporting_duration_calendar_days", 14))

        writing = self.timeline.calendar.add_working_days(sprint_start, writing_days)
        internal_review = self.timeline.calendar.add_working_days(writing, internal_review_days)
        client_review = self.timeline.calendar.add_working_days(internal_review, client_review_days)
        publishing = self.timeline.calendar.add_working_days(client_review, publish_after_client_days)
        promoting = self.timeline.calendar.next_working_day_on_or_after(sprint_start + timedelta(days=max(promotion_days, 0)))
        reporting = self.timeline.calendar.next_working_day_on_or_after(promoting + timedelta(days=max(reporting_days, 0)))

        if deliverable_type == DeliverableType.LEAD_TOTAL:
            target = sow_end_date or reporting
            return self.timeline.calendar.next_working_day_on_or_after(target)

        by_type = {
            DeliverableType.KICKOFF_CALL: self.timeline.calendar.next_working_day_on_or_after(sprint_start),
            DeliverableType.INTERVIEW_CALL: self.timeline.calendar.add_working_days(sprint_start, 6),
            DeliverableType.ARTICLE: publishing,
            DeliverableType.VIDEO: publishing,
            DeliverableType.CLIP: publishing,
            DeliverableType.SHORT: publishing,
            DeliverableType.REPORT: reporting,
            DeliverableType.ENGAGEMENT_LIST: reporting,
            DeliverableType.LANDING_PAGE: publishing,
            DeliverableType.EMAIL: publishing,
            DeliverableType.DISPLAY_ASSET: promoting,
        }
        return by_type.get(deliverable_type, publishing)
