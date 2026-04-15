from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    ActivityLog,
    Campaign,
    CampaignAssignment,
    CapacityLedger,
    Deal,
    Deliverable,
    RoleName,
    ReviewWindow,
    ReviewWindowStatus,
    TemplateVersion,
    WaitingOnType,
    WorkflowStep,
)
from app.services.calendar_service import build_default_working_calendar
from app.services.ops_defaults_service import OpsDefaultsService
from app.services.timeline_service import TimelineService


SEVERITY_ORDER = {"not_started": 0, "on_track": 1, "at_risk": 2, "off_track": 3}


@dataclass
class CampaignHealthResult:
    campaign_id: str
    overall_status: str
    worst_signal: dict[str, Any] | None
    dimension_scores: dict[str, str]
    next_action: dict[str, Any] | None
    checkpoint_health: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


class CampaignHealthService:
    def __init__(self, db: Session):
        self.db = db
        self.timeline = TimelineService(build_default_working_calendar())
        self.ops_defaults = OpsDefaultsService(db).get()

    def evaluate_campaign(self, campaign: Campaign) -> CampaignHealthResult:
        deliverables = self.db.scalars(select(Deliverable).where(Deliverable.campaign_id == campaign.id)).all()
        deliverables_by_id = {d.id: d for d in deliverables}
        deliverable_ids = [d.id for d in deliverables]
        review_windows = (
            self.db.scalars(
                select(ReviewWindow).where(
                    ReviewWindow.deliverable_id.in_(deliverable_ids),
                    ReviewWindow.status == ReviewWindowStatus.OPEN,
                )
            ).all()
            if deliverable_ids
            else []
        )
        steps = self.db.scalars(
            select(WorkflowStep).where(
                (WorkflowStep.campaign_id == campaign.id)
                | (WorkflowStep.linked_deliverable_id.in_(deliverable_ids))
            )
        ).all()
        open_steps = [s for s in steps if s.actual_done is None]
        step_ids = [s.id for s in open_steps]
        step_activity = (
            self.db.scalars(
                select(ActivityLog).where(
                    ActivityLog.entity_type == "workflow_step",
                    ActivityLog.entity_id.in_(step_ids),
                )
            ).all()
            if step_ids
            else []
        )

        critical_step_names = self._critical_step_names(campaign.template_version_id)
        now = datetime.utcnow()
        today = now.date()

        dimension_signals: dict[str, list[dict[str, Any]]] = {
            "timeliness": [],
            "stagnation": [],
            "dependency_blockage": [],
            "replanning": [],
        }
        checkpoint_health: list[dict[str, Any]] = []
        all_signals: list[dict[str, Any]] = []

        replan_map = self._replan_push_count_by_step(step_activity)

        for step in open_steps:
            linked_deliverable_id = self._linked_deliverable_id(step)
            deliverable = deliverables_by_id.get(linked_deliverable_id) if linked_deliverable_id else None
            step_label = f"{step.name}"
            is_critical_checkpoint = step.name.lower() in critical_step_names
            overdue_working_days = self._overdue_working_days(step.current_due, today)
            push_count = replan_map.get(step.id, 0)
            threshold = self._stuck_threshold(step)

            step_signals: list[dict[str, Any]] = []

            # Timeliness
            if overdue_working_days >= 5 and is_critical_checkpoint:
                sig = self._signal(
                    "timeliness",
                    "off_track",
                    "critical checkpoint overdue by 5+ working days",
                    step,
                    deliverable,
                    {"overdue_working_days": overdue_working_days},
                )
                step_signals.append(sig)
                dimension_signals["timeliness"].append(sig)
            elif overdue_working_days >= 1:
                sig = self._signal(
                    "timeliness",
                    "at_risk",
                    "checkpoint overdue by 1+ working day",
                    step,
                    deliverable,
                    {"overdue_working_days": overdue_working_days},
                )
                step_signals.append(sig)
                dimension_signals["timeliness"].append(sig)
            elif step.baseline_due and step.current_due and step.current_due > step.baseline_due:
                drift_days = self.timeline.variance_working_days(step.baseline_due, step.current_due)
                sig = self._signal(
                    "timeliness",
                    "on_track",
                    "forecast due has moved later than baseline",
                    step,
                    deliverable,
                    {"variance_working_days": drift_days},
                )
                step_signals.append(sig)
                dimension_signals["timeliness"].append(sig)

            # Stagnation
            stagnant_age = self._stagnation_age_days(step, now)
            if stagnant_age is not None:
                if stagnant_age >= (2 * threshold):
                    sig = self._signal(
                        "stagnation",
                        "off_track",
                        "step has stagnated for >= 2x threshold",
                        step,
                        deliverable,
                        {"age_days": stagnant_age, "threshold_days": threshold},
                    )
                    step_signals.append(sig)
                    dimension_signals["stagnation"].append(sig)
                elif stagnant_age >= threshold:
                    sig = self._signal(
                        "stagnation",
                        "at_risk",
                        "step has stagnated beyond threshold",
                        step,
                        deliverable,
                        {"age_days": stagnant_age, "threshold_days": threshold},
                    )
                    step_signals.append(sig)
                    dimension_signals["stagnation"].append(sig)

            # Dependency blockage
            if step.waiting_on_type == WaitingOnType.DEPENDENCY:
                dep_age = self._waiting_age_days(step, now)
                if dep_age >= (2 * threshold):
                    sig = self._signal(
                        "dependency_blockage",
                        "off_track",
                        "dependency blockage >= 2x threshold",
                        step,
                        deliverable,
                        {"age_days": dep_age, "threshold_days": threshold},
                    )
                    step_signals.append(sig)
                    dimension_signals["dependency_blockage"].append(sig)
                elif dep_age >= threshold:
                    sig = self._signal(
                        "dependency_blockage",
                        "at_risk",
                        "dependency blockage beyond threshold",
                        step,
                        deliverable,
                        {"age_days": dep_age, "threshold_days": threshold},
                    )
                    step_signals.append(sig)
                    dimension_signals["dependency_blockage"].append(sig)

            # Replanning
            if push_count >= 3 and overdue_working_days >= 1:
                sig = self._signal(
                    "replanning",
                    "off_track",
                    "due date pushed 3+ times and currently overdue",
                    step,
                    deliverable,
                    {"replan_push_count": push_count},
                )
                step_signals.append(sig)
                dimension_signals["replanning"].append(sig)
            elif push_count >= 2:
                sig = self._signal(
                    "replanning",
                    "at_risk",
                    "due date pushed 2+ times with reason",
                    step,
                    deliverable,
                    {"replan_push_count": push_count},
                )
                step_signals.append(sig)
                dimension_signals["replanning"].append(sig)
            elif push_count >= 1:
                sig = self._signal(
                    "replanning",
                    "on_track",
                    "due date pushed later once",
                    step,
                    deliverable,
                    {"replan_push_count": push_count},
                )
                step_signals.append(sig)
                dimension_signals["replanning"].append(sig)

            worst_for_step = self._worst_signal(step_signals)
            checkpoint_health.append(
                {
                    "step_id": step.display_id,
                    "step_name": step.name,
                    "deliverable_id": deliverable.display_id if deliverable else None,
                    "deliverable_title": deliverable.title if deliverable else None,
                    "status": worst_for_step["severity"] if worst_for_step else "not_started",
                    "reason": worst_for_step["reason"] if worst_for_step else "Not started",
                    "owner_user_id": step.next_owner_user_id,
                    "owner_role": step.owner_role.value,
                    "current_due": step.current_due.isoformat() if step.current_due else None,
                    "waiting_on_type": step.waiting_on_type.value if step.waiting_on_type else None,
                    "blocker_reason": step.blocker_reason,
                }
            )

        for sigs in dimension_signals.values():
            all_signals.extend(sigs)

        for window in review_windows:
            deliverable = deliverables_by_id.get(window.deliverable_id)
            overdue_working_days = self._overdue_working_days(window.window_due, today)
            if overdue_working_days <= 0:
                continue
            sev = "off_track" if overdue_working_days >= 5 else "at_risk"
            sig = {
                "dimension": "timeliness",
                "severity": sev,
                "reason": f"{window.window_type.value.replace('_', ' ')} window overdue",
                "step_id": None,
                "step_internal_id": None,
                "step_name": f"{window.window_type.value} window",
                "deliverable_id": deliverable.display_id if deliverable else None,
                "deliverable_title": deliverable.title if deliverable else None,
                "owner_user_id": deliverable.owner_user_id if deliverable else None,
                "owner_role": None,
                "due": window.window_due.isoformat(),
                "overdue_working_days": overdue_working_days,
            }
            all_signals.append(sig)
            dimension_signals["timeliness"].append(sig)

        overall_status = self._worst_severity([s["severity"] for s in all_signals]) or "not_started"
        worst_signal = self._worst_signal(all_signals)
        dimension_scores = {
            name: (self._worst_severity([s["severity"] for s in sigs]) or "not_started")
            for name, sigs in dimension_signals.items()
        }
        warnings = self._capacity_compression_warnings(campaign, open_steps)
        next_action = self._next_action(overall_status, worst_signal, open_steps, campaign.id)

        return CampaignHealthResult(
            campaign_id=campaign.id,
            overall_status=overall_status,
            worst_signal=worst_signal,
            dimension_scores=dimension_scores,
            next_action=next_action,
            checkpoint_health=checkpoint_health,
            warnings=warnings,
        )

    def evaluate_campaign_display(self, campaign: Campaign) -> dict[str, Any]:
        health = self.evaluate_campaign(campaign)
        return self._serialize_health(campaign, health)

    def evaluate_many(
        self,
        campaigns: list[Campaign],
        owner: str | None = None,
        status: str | None = None,
        publication: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        deals_by_id = {
            d.id: d
            for d in self.db.scalars(select(Deal).where(Deal.id.in_([c.deal_id for c in campaigns]))).all()
        } if campaigns else {}
        assignment_rows = self.db.scalars(select(CampaignAssignment)).all()
        owners_by_campaign: dict[str, set[str]] = {}
        for a in assignment_rows:
            owners_by_campaign.setdefault(a.campaign_id, set()).add(a.user_id)

        selected = campaigns
        if owner:
            selected = [c for c in selected if owner in owners_by_campaign.get(c.id, set())]
        if publication:
            selected = [c for c in selected if deals_by_id.get(c.deal_id) and deals_by_id[c.deal_id].brand_publication.value == publication]

        rows = [self._serialize_health(c, self.evaluate_campaign(c), deals_by_id.get(c.deal_id), owners_by_campaign.get(c.id, set())) for c in selected]
        if status:
            rows = [r for r in rows if r["overall_status"] == status]
        total = len(rows)
        return {"items": rows[offset : offset + limit], "total": total, "limit": limit, "offset": offset}

    def escalatable(self, health: CampaignHealthResult) -> tuple[bool, str]:
        worst = health.worst_signal
        if worst and worst["severity"] == "off_track":
            return True, f"Off-track health signal: {worst['dimension']} ({worst['reason']})"
        if worst and worst["severity"] == "at_risk":
            if worst.get("age_days", 0) >= 3:
                return True, f"At-risk signal persisted >=3 days: {worst['dimension']}"
        if worst and worst["dimension"] == "stagnation":
            threshold = int(worst.get("threshold_days") or 0)
            age = int(worst.get("age_days") or 0)
            if threshold > 0 and age >= (2 * threshold):
                return True, "Review/workflow stagnation exceeded 2x threshold"
        return False, ""

    def health_risk_signals(self, health: CampaignHealthResult) -> list[dict[str, Any]]:
        signals = []
        for cp in health.checkpoint_health:
            sev = cp["status"]
            if sev not in {"at_risk", "off_track"}:
                continue
            signals.append(
                {
                    "severity": sev,
                    "dimension": "checkpoint_health",
                    "reason": cp["reason"],
                    "step_id": cp["step_id"],
                    "step_name": cp["step_name"],
                    "owner_user_id": cp["owner_user_id"],
                    "owner_role": cp["owner_role"],
                }
            )
        if health.worst_signal and health.worst_signal["severity"] in {"at_risk", "off_track"}:
            signals.append(health.worst_signal)
        return signals

    def _serialize_health(
        self,
        campaign: Campaign,
        health: CampaignHealthResult,
        deal: Deal | None = None,
        owner_user_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "campaign_id": campaign.display_id,
            "campaign_internal_id": campaign.id,
            "title": campaign.title,
            "type": campaign.campaign_type.value,
            "tier": campaign.tier,
            "publication": deal.brand_publication.value if deal else None,
            "owner_user_ids": sorted(list(owner_user_ids or set())),
            "overall_status": health.overall_status,
            "worst_signal": health.worst_signal,
            "dimension_scores": health.dimension_scores,
            "next_action": health.next_action,
            "warnings": health.warnings,
        }

    @staticmethod
    def _linked_deliverable_id(step: WorkflowStep) -> str | None:
        return step.linked_deliverable_id

    def _signal(
        self,
        dimension: str,
        severity: str,
        reason: str,
        step: WorkflowStep,
        deliverable: Deliverable | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "dimension": dimension,
            "severity": severity,
            "reason": reason,
            "step_id": step.display_id,
            "step_internal_id": step.id,
            "step_name": step.name,
            "deliverable_id": deliverable.display_id if deliverable else None,
            "deliverable_title": deliverable.title if deliverable else None,
            "owner_user_id": step.next_owner_user_id,
            "owner_role": step.owner_role.value,
            "due": step.current_due.isoformat() if step.current_due else None,
        }
        if extra:
            payload.update(extra)
        return payload

    def _worst_signal(self, signals: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not signals:
            return None
        return sorted(signals, key=lambda s: (SEVERITY_ORDER.get(s["severity"], 0), s.get("due") or "9999-12-31"), reverse=True)[0]

    def _worst_severity(self, severities: list[str]) -> str | None:
        if not severities:
            return None
        return sorted(severities, key=lambda s: SEVERITY_ORDER.get(s, 0), reverse=True)[0]

    def _critical_step_names(self, template_version_id: str) -> set[str]:
        template = self.db.get(TemplateVersion, template_version_id)
        if not template:
            return {"create content plan", "run interview", "internal review", "client review", "final approval"}
        critical: set[str] = set()
        workflow = template.workflow_json or {}
        by_deliverable = workflow.get("steps_by_deliverable", {}) or {}
        by_sprint_legacy = workflow.get("steps_by_sprint", {}) or {}
        by_sprint_phase = workflow.get("steps_by_sprint_phase", {}) or {}
        for steps in list(by_deliverable.values()) + list(by_sprint_legacy.values()) + list(by_sprint_phase.values()):
            for step in steps:
                if bool(step.get("health_critical")):
                    critical.add(str(step.get("name", "")).strip().lower())
        if not critical:
            critical = {"create content plan", "run interview", "internal review", "client review", "final approval"}
        return critical

    def _overdue_working_days(self, current_due: date | None, today: date) -> int:
        if not current_due or current_due >= today:
            return 0
        return max(self.timeline.working_days_between(current_due, today), 0)

    def _waiting_age_days(self, step: WorkflowStep, now: datetime) -> int:
        if not step.waiting_since:
            return 0
        return max((now - step.waiting_since).days, 0)

    def _stagnation_age_days(self, step: WorkflowStep, now: datetime) -> int | None:
        if step.waiting_since:
            return max((now - step.waiting_since).days, 0)
        if step.actual_start:
            return max((now - step.actual_start).days, 0)
        return None

    def _stuck_threshold(self, step: WorkflowStep) -> int:
        if step.stuck_threshold_days and step.stuck_threshold_days > 0:
            return int(step.stuck_threshold_days)
        defaults = (self.ops_defaults.get("timeline_defaults") or {})
        return int(defaults.get("internal_review_working_days", 2))

    def _replan_push_count_by_step(self, activity: list[ActivityLog]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in activity:
            if a.action != "workflow_step_due_overridden":
                continue
            meta = a.meta_json or {}
            old_due_raw = meta.get("old_due")
            new_due_raw = meta.get("new_due")
            reason_code = meta.get("reason_code")
            if not old_due_raw or not new_due_raw or not reason_code:
                continue
            try:
                old_due = date.fromisoformat(str(old_due_raw))
                new_due = date.fromisoformat(str(new_due_raw))
            except ValueError:
                continue
            if new_due > old_due:
                counts[a.entity_id] = counts.get(a.entity_id, 0) + 1
        return counts

    def _next_action(self, overall_status: str, worst_signal: dict[str, Any] | None, open_steps: list[WorkflowStep], campaign_id: str) -> dict[str, Any] | None:
        if worst_signal:
            escalate = overall_status == "off_track"
            action = "Review and resolve highest-risk checkpoint"
            dim = worst_signal.get("dimension")
            if dim == "dependency_blockage":
                action = "Unblock dependency and restart downstream flow"
            elif dim == "stagnation":
                action = "Move stalled checkpoint forward or reassign owner"
            elif dim == "timeliness":
                action = "Recover overdue checkpoint against milestone plan"
            elif dim == "replanning":
                action = "Stop date churn and lock a realistic forecast plan"
            return {
                "campaign_id": campaign_id,
                "action": action,
                "owner_user_id": worst_signal.get("owner_user_id"),
                "owner_role": worst_signal.get("owner_role"),
                "due": worst_signal.get("due"),
                "step_id": worst_signal.get("step_id"),
                "escalate": escalate,
                "trigger_signal": dim,
            }

        if not open_steps:
            return None
        sorted_steps = sorted(open_steps, key=lambda s: (s.current_due or date.max, s.created_at))
        first = sorted_steps[0]
        return {
            "campaign_id": campaign_id,
            "action": "Continue next planned checkpoint",
            "owner_user_id": first.next_owner_user_id,
            "owner_role": first.owner_role.value,
            "due": first.current_due.isoformat() if first.current_due else None,
            "step_id": first.display_id,
            "escalate": False,
            "trigger_signal": None,
        }

    def _capacity_compression_warnings(self, campaign: Campaign, open_steps: list[WorkflowStep]) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        current_week = date.today() - timedelta(days=date.today().weekday())
        horizon_week = current_week + timedelta(days=28)
        assignments = self.db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign.id)).all()
        for a in assignments:
            rows = self.db.scalars(
                select(CapacityLedger).where(
                    CapacityLedger.user_id == a.user_id,
                    CapacityLedger.role_name == a.role_name,
                    CapacityLedger.week_start >= current_week,
                    CapacityLedger.week_start <= horizon_week,
                )
            ).all()
            for r in rows:
                if r.forecast_planned_hours > r.capacity_hours and not r.override_approved:
                    warnings.append(
                        {
                            "type": "capacity",
                            "severity": "on_track",
                            "reason": (
                                f"{a.role_name.value} forecast {r.forecast_planned_hours:.1f}h exceeds "
                                f"capacity {r.capacity_hours:.1f}h in week {r.week_start.isoformat()}"
                            ),
                            "owner_user_id": a.user_id,
                            "week_start": r.week_start.isoformat(),
                        }
                    )

        # Compression warning: too many open steps due soon.
        today = date.today()
        soon_due = [
            s
            for s in open_steps
            if s.current_due and s.current_due >= today and self.timeline.working_days_between(today, s.current_due) <= 5
        ]
        if len(open_steps) >= 4 and len(soon_due) >= max(3, int(len(open_steps) * 0.4)):
            warnings.append(
                {
                    "type": "compression",
                    "severity": "on_track",
                    "reason": f"{len(soon_due)} open checkpoints are due within 5 working days",
                    "owner_user_id": None,
                }
            )
        return warnings
