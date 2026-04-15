from __future__ import annotations

from datetime import datetime, timezone

from app.models.domain import RiskSeverity, WorkflowStep


class RiskService:
    def evaluate_step_risk(self, step: WorkflowStep) -> tuple[str, RiskSeverity] | None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if step.actual_done is None and step.current_due is not None and step.current_due < now.date():
            return ("step_overdue", RiskSeverity.HIGH)

        if step.waiting_since and step.stuck_threshold_days > 0:
            delta_days = (now - step.waiting_since).days
            if delta_days >= step.stuck_threshold_days:
                return ("step_stalled_waiting", RiskSeverity.MEDIUM)

        return None
