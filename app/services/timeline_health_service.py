from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    Campaign,
    CampaignAssignment,
    Deal,
    Deliverable,
    DeliverableStage,
    GlobalHealth,
    GlobalStatus,
    OpsDefaultConfig,
    RoleName,
    Stage,
    WorkflowStep,
    WorkflowStepEffort,
)
from app.services.calendar_service import build_default_working_calendar
from app.services.timeline_service import TimelineService


SEVERITY_ORDER = {"not_started": 0, "on_track": 1, "at_risk": 2, "off_track": 3}


@dataclass
class HealthEvaluation:
    health: str
    health_reason: str
    buffer_working_days_remaining: int | None
    is_not_due: bool


class TimelineHealthService:
    def __init__(self, db: Session):
        self.db = db
        self.timeline = TimelineService(build_default_working_calendar())
        self.defaults = self._defaults()

    def evaluate_step(self, step: WorkflowStep, campaign: Campaign | None = None) -> HealthEvaluation:
        start = (
            step.earliest_start_date
            or step.current_start
            or step.baseline_start
            or (campaign.planned_start_date if campaign else None)
        )
        due = step.current_due or step.baseline_due or (campaign.planned_end_date if campaign else None)
        status = self._step_status(step)
        return self._evaluate_window(
            object_type="step",
            status=status,
            start=start,
            due=due,
            stage_key="default",
            remaining_hours=max(float(step.planned_hours or 0.0), 0.0) if step.actual_done is None else 0.0,
            required_working_days=None,
            role_capacities=[self._capacity_for_role(step.owner_role)],
            parent_child_worst=None,
        )

    def evaluate_deliverable(
        self,
        deliverable: Deliverable,
        campaign: Campaign | None,
        steps: list[WorkflowStep],
        efforts_by_step_id: dict[str, list[WorkflowStepEffort]],
    ) -> HealthEvaluation:
        stage_key = (deliverable.stage.value if isinstance(deliverable.stage, DeliverableStage) else str(deliverable.stage or "default")).lower()
        start_candidates = [s.current_start for s in steps if s.current_start] + [s.baseline_start for s in steps if s.baseline_start]
        start = min(start_candidates) if start_candidates else (campaign.planned_start_date if campaign else None)
        due = deliverable.current_due or deliverable.baseline_due or (max([s.current_due for s in steps if s.current_due], default=None)) or (campaign.planned_end_date if campaign else None)
        child_health = [self.evaluate_step(s, campaign=campaign).health for s in steps]
        remaining_hours = 0.0
        role_caps: list[float] = []
        for step in steps:
            if step.actual_done is not None:
                continue
            step_remaining = max(float(step.planned_hours or 0.0), 0.0)
            remaining_hours += step_remaining
            efforts = efforts_by_step_id.get(step.id, [])
            if efforts:
                for eff in efforts:
                    role_caps.append(self._capacity_for_role(eff.role_name))
            else:
                role_caps.append(self._capacity_for_role(step.owner_role))
        return self._evaluate_window(
            object_type="deliverable",
            status=self._deliverable_status(deliverable),
            start=start,
            due=due,
            stage_key=stage_key,
            remaining_hours=remaining_hours,
            required_working_days=None,
            role_capacities=role_caps,
            parent_child_worst=self._worst(child_health),
        )

    def evaluate_stage(
        self,
        stage: Stage,
        campaign: Campaign | None,
        steps: list[WorkflowStep],
        efforts_by_step_id: dict[str, list[WorkflowStepEffort]],
    ) -> HealthEvaluation:
        start = stage.current_start or stage.baseline_start or (campaign.planned_start_date if campaign else None)
        due = stage.current_due or stage.baseline_due or (campaign.planned_end_date if campaign else None)
        child_health = [self.evaluate_step(s, campaign=campaign).health for s in steps]
        remaining_hours = 0.0
        required_turnaround_days = 0
        role_caps: list[float] = []
        for step in steps:
            if step.actual_done is not None:
                continue
            remaining_hours += max(float(step.planned_hours or 0.0), 0.0)
            required_turnaround_days += self._step_turnaround_days(step, campaign)
            efforts = efforts_by_step_id.get(step.id, [])
            if efforts:
                role_caps.extend(self._capacity_for_role(eff.role_name) for eff in efforts)
            else:
                role_caps.append(self._capacity_for_role(step.owner_role))
        status = self._stage_status(stage, child_steps=steps)
        return self._evaluate_window(
            object_type="stage",
            status=status,
            start=start,
            due=due,
            stage_key=str(stage.name or "default").lower(),
            remaining_hours=remaining_hours,
            required_working_days=float(required_turnaround_days),
            role_capacities=role_caps or [self._capacity_for_role(RoleName.CM)],
            parent_child_worst=self._worst(child_health),
        )

    def evaluate_campaign(
        self,
        campaign: Campaign,
        deliverables: list[Deliverable],
        steps: list[WorkflowStep],
        efforts_by_step_id: dict[str, list[WorkflowStepEffort]],
        assignments: list[CampaignAssignment],
        stages: list[Stage] | None = None,
    ) -> tuple[HealthEvaluation, str]:
        derived_stage = self._derive_campaign_stage(deliverables)
        start = campaign.planned_start_date
        if not start:
            start = min([d.current_due for d in deliverables if d.current_due], default=None)
        due = campaign.planned_end_date
        if not due:
            due = max([d.current_due for d in deliverables if d.current_due], default=None)
        child_health = []
        stage_healths: list[str] = []
        remaining_hours = 0.0
        required_turnaround_days = 0
        role_caps: list[float] = []
        steps_by_deliverable: dict[str, list[WorkflowStep]] = {}
        for s in steps:
            linked_deliverable_id = s.linked_deliverable_id
            if linked_deliverable_id:
                steps_by_deliverable.setdefault(linked_deliverable_id, []).append(s)
        for d in deliverables:
            d_health = self.evaluate_deliverable(d, campaign, steps_by_deliverable.get(d.id, []), efforts_by_step_id)
            child_health.append(d_health.health)
        if not deliverables:
            for s in steps:
                child_health.append(self.evaluate_step(s, campaign=campaign).health)
        stages = stages or self.db.scalars(select(Stage).where(Stage.campaign_id == campaign.id)).all()
        steps_by_stage: dict[str, list[WorkflowStep]] = {}
        for s in steps:
            if s.stage_id:
                steps_by_stage.setdefault(s.stage_id, []).append(s)
        for st in stages:
            st_eval = self.evaluate_stage(st, campaign=campaign, steps=steps_by_stage.get(st.id, []), efforts_by_step_id=efforts_by_step_id)
            stage_healths.append(st_eval.health)
            child_health.append(st_eval.health)
        assignment_caps = [self._capacity_for_role(a.role_name) for a in assignments]
        for s in steps:
            if s.actual_done is not None:
                continue
            remaining_hours += max(float(s.planned_hours or 0.0), 0.0)
            required_turnaround_days += self._step_turnaround_days(s, campaign)
        role_caps = assignment_caps or [self._capacity_for_role(RoleName.CM)]
        evaluation = self._evaluate_window(
            object_type="campaign",
            status=self._campaign_status(campaign),
            start=start,
            due=due,
            stage_key=derived_stage,
            remaining_hours=remaining_hours,
            required_working_days=float(required_turnaround_days),
            role_capacities=role_caps,
            parent_child_worst=None,
        )
        worst_stage = self._worst(stage_healths)
        worst_child = self._worst(child_health)
        if worst_stage == "off_track" and evaluation.health != "off_track":
            evaluation = HealthEvaluation(
                health="off_track",
                health_reason="stage_off_track_rollup",
                buffer_working_days_remaining=evaluation.buffer_working_days_remaining,
                is_not_due=evaluation.is_not_due,
            )
        elif evaluation.health == "on_track" and worst_child in {"off_track", "at_risk"}:
            evaluation = HealthEvaluation(
                health="at_risk",
                health_reason="child_timeline_signal_campaign_still_feasible",
                buffer_working_days_remaining=evaluation.buffer_working_days_remaining,
                is_not_due=evaluation.is_not_due,
            )
        elif evaluation.health == "on_track":
            child_block = self._rollup_guard(worst_child)
            if child_block:
                evaluation = HealthEvaluation(
                    health="at_risk",
                    health_reason="child_timeline_signal_campaign_still_feasible",
                    buffer_working_days_remaining=evaluation.buffer_working_days_remaining,
                    is_not_due=evaluation.is_not_due,
                )
        return evaluation, derived_stage

    def evaluate_scope(self, deal: Deal, campaigns_data: list[tuple[Campaign, HealthEvaluation]]) -> HealthEvaluation:
        child_health = [h.health for _, h in campaigns_data]
        start = deal.sow_start_date
        due = deal.sow_end_date
        status = "done" if campaigns_data and all(h.health == "on_track" for _, h in campaigns_data) and date.today() > (due or date.today()) else "in_progress"
        return self._evaluate_window(
            object_type="scope",
            status=status,
            start=start,
            due=due,
            stage_key="default",
            remaining_hours=0.0,
            required_working_days=None,
            role_capacities=[self._capacity_for_role(RoleName.AM)],
            parent_child_worst=self._worst(child_health),
        )

    def _evaluate_window(
        self,
        object_type: str,
        status: str,
        start: date | None,
        due: date | None,
        stage_key: str,
        remaining_hours: float,
        required_working_days: float | None,
        role_capacities: list[float],
        parent_child_worst: str | None,
    ) -> HealthEvaluation:
        today = date.today()
        if start is None or due is None:
            return HealthEvaluation(
                health="at_risk",
                health_reason="data_incomplete",
                buffer_working_days_remaining=None,
                is_not_due=False,
            )
        if today < start:
            return HealthEvaluation("not_started", "before_planned_window", self.timeline.working_days_between(today, due), True)
        if status in {"done", "cancelled"}:
            child_block = self._rollup_guard(parent_child_worst)
            if child_block:
                return child_block
            return HealthEvaluation("on_track", "completed_or_cancelled", 0, False)

        remaining_working_days = max(self.timeline.working_days_between(today, due), 0)
        threshold = self._buffer_threshold(object_type, stage_key)
        capacity_per_day = self._daily_capacity(role_capacities)
        feasible_capacity_hours = remaining_working_days * capacity_per_day
        needs_days = max(float(required_working_days or 0.0), 0.0)
        cannot_fit_hours = remaining_hours > 0 and feasible_capacity_hours + 1e-6 < remaining_hours
        cannot_fit_turnaround = needs_days > 0 and (remaining_working_days + 1e-6) < needs_days
        if today > due or cannot_fit_hours or cannot_fit_turnaround:
            return HealthEvaluation("off_track", "cannot_complete_before_due", remaining_working_days, False)
        if remaining_working_days <= threshold:
            return HealthEvaluation("at_risk", "low_timeline_buffer", remaining_working_days, False)
        child_block = self._rollup_guard(parent_child_worst)
        if child_block:
            return child_block
        return HealthEvaluation("on_track", "sufficient_buffer_and_capacity", remaining_working_days, False)

    def _rollup_guard(self, parent_child_worst: str | None) -> HealthEvaluation | None:
        if parent_child_worst == "off_track":
            return HealthEvaluation("off_track", "child_off_track_rollup", None, False)
        if parent_child_worst == "at_risk":
            return HealthEvaluation("at_risk", "child_at_risk_rollup", None, False)
        return None

    def _defaults(self) -> dict[str, Any]:
        row = self.db.scalar(select(OpsDefaultConfig).where(OpsDefaultConfig.config_key == "global"))
        payload = (row.config_json if row else {}) or {}
        return payload

    def _buffer_threshold(self, object_type: str, stage_key: str) -> int:
        cfg = (self.defaults.get("health_buffer_days") or {}).get(object_type) or {}
        if stage_key in cfg:
            return max(int(cfg.get(stage_key, 0)), 0)
        return max(int(cfg.get("default", 0)), 0)

    def _capacity_for_role(self, role: RoleName) -> float:
        cap = self.defaults.get("capacity_hours_per_week") or {}
        return max(float(cap.get(role.value.lower(), 16.0)), 0.0)

    def _step_turnaround_days(self, step: WorkflowStep, campaign: Campaign | None) -> int:
        baseline_start = step.baseline_start
        baseline_due = step.baseline_due
        if baseline_start and baseline_due:
            return max(self.timeline.working_days_between(baseline_start, baseline_due), 1)
        current_start = step.current_start or campaign.planned_start_date if campaign else step.current_start
        current_due = step.current_due or campaign.planned_end_date if campaign else step.current_due
        if current_start and current_due:
            return max(self.timeline.working_days_between(current_start, current_due), 1)
        return 1

    @staticmethod
    def _daily_capacity(role_capacities: list[float]) -> float:
        if not role_capacities:
            return 8.0
        return max(sum(role_capacities) / 4.0, 1.0)

    @staticmethod
    def _step_status(step: WorkflowStep) -> str:
        if step.actual_done:
            return "done"
        if step.normalized_status:
            return step.normalized_status.value
        return "not_started"

    @staticmethod
    def _deliverable_status(deliverable: Deliverable) -> str:
        raw = deliverable.status.value
        if raw in {"complete"}:
            return "done"
        return raw

    @staticmethod
    def _campaign_status(campaign: Campaign) -> str:
        return str(campaign.status or "not_started").strip().lower()

    @staticmethod
    def _stage_status(stage: Stage, child_steps: list[WorkflowStep]) -> str:
        if stage.status:
            return str(stage.status.value if hasattr(stage.status, "value") else stage.status).strip().lower()
        if not child_steps:
            return "not_started"
        if all(s.actual_done is not None for s in child_steps):
            return "done"
        if any((s.normalized_status and s.normalized_status.value.startswith("blocked")) for s in child_steps):
            blocked = next((s.normalized_status.value for s in child_steps if s.normalized_status and s.normalized_status.value.startswith("blocked")), "blocked_internal")
            return blocked
        if any(s.actual_start is not None for s in child_steps):
            return "in_progress"
        return "not_started"

    @staticmethod
    def _worst(healths: list[str]) -> str | None:
        if not healths:
            return None
        return sorted(healths, key=lambda v: SEVERITY_ORDER.get(v, 0), reverse=True)[0]

    @staticmethod
    def _derive_campaign_stage(deliverables: list[Deliverable]) -> str:
        if not deliverables:
            return "not_started"
        stage_order = {"planning": 0, "production": 1, "promotion": 2, "reporting": 3}
        open_deliverables = [d for d in deliverables if d.status.value not in {"complete"}]
        if not open_deliverables:
            return "reporting"
        highest = max(
            (stage_order.get((d.stage.value if isinstance(d.stage, DeliverableStage) else str(d.stage or "planning")).lower(), 0) for d in open_deliverables),
            default=0,
        )
        return next((k for k, v in stage_order.items() if v == highest), "planning")
