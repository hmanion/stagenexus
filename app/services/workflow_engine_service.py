from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import (
    CampaignAssignment,
    Deliverable,
    GlobalHealth,
    GlobalStatus,
    Stage,
    WaitingOnType,
    WorkflowStep,
    WorkflowStepDependency,
    WorkflowStepEffort,
    User,
)
from app.services.calendar_service import build_default_working_calendar
from app.services.timeline_service import TimelineService


class WorkflowEngineService:
    def __init__(self, db: Session):
        self.db = db
        self.timeline = TimelineService(build_default_working_calendar())

    def set_step_complete(
        self,
        step_id: str,
        actor_user_id: str,
        enforce_next_owner: bool = True,
    ) -> WorkflowStep:
        step = self.db.get(WorkflowStep, step_id) or self.db.scalar(
            select(WorkflowStep).where(WorkflowStep.display_id == step_id)
        )
        if not step:
            raise HTTPException(status_code=404, detail="workflow step not found")

        if enforce_next_owner and step.next_owner_user_id and step.next_owner_user_id != actor_user_id:
            raise HTTPException(status_code=403, detail="actor is not the next owner for this step")

        now = datetime.utcnow()
        step.actual_start = step.actual_start or now
        step.actual_done = now
        step.waiting_on_type = None
        step.waiting_on_user_id = None
        step.waiting_since = None
        step.blocker_reason = None
        step.normalized_status = GlobalStatus.DONE
        step.normalized_health = GlobalHealth.ON_TRACK

        self._activate_successors(step)
        self._refresh_stage_from_steps(step.stage_id)
        return step

    def override_step_due(self, step_id: str, current_due_iso: str) -> WorkflowStep:
        step = self.db.get(WorkflowStep, step_id) or self.db.scalar(
            select(WorkflowStep).where(WorkflowStep.display_id == step_id)
        )
        if not step:
            raise HTTPException(status_code=404, detail="workflow step not found")

        raw_due = datetime.fromisoformat(current_due_iso).date()
        new_due = self.timeline.calendar.next_working_day_on_or_after(raw_due)
        if step.current_start is None:
            step.current_start = self.timeline.calendar.next_working_day_on_or_after(datetime.utcnow().date())
        step.current_due = new_due

        self._recalculate_successor_chain(step)
        return step

    def manage_step(
        self,
        step_id: str,
        actor_user_id: str,
        status: str | None = None,
        next_owner_user_id: str | None = None,
        waiting_on_user_id: str | None = None,
        blocker_reason: str | None = None,
        current_start_iso: str | None = None,
        current_due_iso: str | None = None,
    ) -> WorkflowStep:
        step = self.db.get(WorkflowStep, step_id) or self.db.scalar(
            select(WorkflowStep).where(WorkflowStep.display_id == step_id)
        )
        if not step:
            raise HTTPException(status_code=404, detail="workflow step not found")

        if next_owner_user_id is not None:
            owner = self.db.get(User, next_owner_user_id)
            if not owner:
                raise HTTPException(status_code=400, detail="next_owner_user_id not found")
            step.next_owner_user_id = next_owner_user_id

        if waiting_on_user_id is not None:
            if waiting_on_user_id:
                waiting_user = self.db.get(User, waiting_on_user_id)
                if not waiting_user:
                    raise HTTPException(status_code=400, detail="waiting_on_user_id not found")
                step.waiting_on_user_id = waiting_on_user_id
            else:
                step.waiting_on_user_id = None

        if current_start_iso:
            raw_start = datetime.fromisoformat(current_start_iso).date()
            step.current_start = self.timeline.calendar.next_working_day_on_or_after(raw_start)

        if current_due_iso:
            raw_due = datetime.fromisoformat(current_due_iso).date()
            step.current_due = self.timeline.calendar.next_working_day_on_or_after(raw_due)
            if step.current_start is None:
                step.current_start = self.timeline.calendar.next_working_day_on_or_after(datetime.utcnow().date())
        if step.current_start and step.current_due and step.current_due < step.current_start:
            step.current_due = step.current_start

        if blocker_reason is not None:
            step.blocker_reason = blocker_reason.strip() or None

        if not status:
            self._refresh_stage_from_steps(step.stage_id)
            return step

        normalized = status.strip().lower()
        normalized = normalized.replace("blocked: ", "blocked_").replace(" ", "_")
        now = datetime.utcnow()

        if normalized in {"complete", "done"}:
            # manage_step is already guarded by control permissions at the API layer.
            # Do not re-block completion based on next-owner identity here.
            result = self.set_step_complete(
                step_id=step_id,
                actor_user_id=actor_user_id,
                enforce_next_owner=False,
            )
            self._refresh_stage_from_steps(result.stage_id)
            return result
        if normalized in {"cancelled", "canceled"}:
            step.actual_done = now
            step.waiting_on_type = None
            step.waiting_on_user_id = None
            step.waiting_since = None
            step.blocker_reason = None
            step.normalized_status = GlobalStatus.CANCELLED
            step.normalized_health = GlobalHealth.OFF_TRACK
            self._refresh_stage_from_steps(step.stage_id)
            return step
        if normalized in {"not_started", "planned"}:
            step.actual_start = None
            step.actual_done = None
            step.waiting_on_type = None
            step.waiting_on_user_id = None
            step.waiting_since = None
            step.blocker_reason = None
            step.normalized_status = GlobalStatus.NOT_STARTED
            step.normalized_health = GlobalHealth.NOT_STARTED
            self._refresh_stage_from_steps(step.stage_id)
            return step
        if normalized == "reopen":
            step.actual_done = None
            step.waiting_on_type = None
            step.waiting_since = None
            if step.current_start is None:
                step.current_start = self.timeline.calendar.next_working_day_on_or_after(now.date())
            step.normalized_status = GlobalStatus.IN_PROGRESS
            step.normalized_health = GlobalHealth.ON_TRACK
            self._refresh_stage_from_steps(step.stage_id)
            return step
        if normalized == "in_progress":
            step.actual_start = step.actual_start or now
            step.actual_done = None
            step.waiting_on_type = None
            step.waiting_since = None
            step.blocker_reason = None
            if step.current_start is None:
                step.current_start = self.timeline.calendar.next_working_day_on_or_after(now.date())
            step.normalized_status = GlobalStatus.IN_PROGRESS
            step.normalized_health = GlobalHealth.ON_TRACK
            self._refresh_stage_from_steps(step.stage_id)
            return step
        if normalized in {"on_hold", "hold"}:
            step.actual_done = None
            step.waiting_on_type = None
            step.waiting_on_user_id = step.waiting_on_user_id
            step.waiting_since = step.waiting_since or now
            step.normalized_status = GlobalStatus.ON_HOLD
            step.normalized_health = GlobalHealth.AT_RISK
            self._refresh_stage_from_steps(step.stage_id)
            return step
        if normalized == "clear_blocker":
            step.waiting_on_type = None
            step.waiting_on_user_id = None
            step.waiting_since = None
            step.blocker_reason = None
            step.normalized_status = GlobalStatus.IN_PROGRESS if step.actual_start else GlobalStatus.NOT_STARTED
            step.normalized_health = GlobalHealth.ON_TRACK if step.actual_start else GlobalHealth.NOT_STARTED
            self._refresh_stage_from_steps(step.stage_id)
            return step

        blocked_map = {
            "blocked_internal": WaitingOnType.INTERNAL,
            "blocked_client": WaitingOnType.CLIENT,
            "blocked_dependency": WaitingOnType.DEPENDENCY,
        }
        waiting_type = blocked_map.get(normalized)
        if waiting_type:
            step.actual_done = None
            step.waiting_on_type = waiting_type
            step.waiting_since = step.waiting_since or now
            if step.current_start is None:
                step.current_start = self.timeline.calendar.next_working_day_on_or_after(now.date())
            if waiting_type == WaitingOnType.CLIENT:
                step.normalized_status = GlobalStatus.BLOCKED_CLIENT
            elif waiting_type == WaitingOnType.INTERNAL:
                step.normalized_status = GlobalStatus.BLOCKED_INTERNAL
            else:
                step.normalized_status = GlobalStatus.BLOCKED_DEPENDENCY
            step.normalized_health = GlobalHealth.AT_RISK
            self._refresh_stage_from_steps(step.stage_id)
            return step

        raise HTTPException(status_code=400, detail="unsupported status action")

    def _activate_successors(self, completed_step: WorkflowStep) -> None:
        successors = self.db.scalars(
            select(WorkflowStep)
            .join(WorkflowStepDependency, WorkflowStepDependency.successor_step_id == WorkflowStep.id)
            .where(WorkflowStepDependency.predecessor_step_id == completed_step.id)
        ).all()

        for successor in successors:
            if successor.actual_done is not None:
                continue

            if self._all_predecessors_done(successor.id):
                start = completed_step.actual_done.date() if completed_step.actual_done else datetime.utcnow().date()
                successor.current_start = self.timeline.calendar.next_working_day_on_or_after(
                    max(successor.current_start or start, start)
                )
                duration = self._duration_working_days(successor)
                successor.current_due = self.timeline.calendar.next_working_day_on_or_after(
                    self.timeline.calendar.add_working_days(successor.current_start, duration)
                )

                successor.next_owner_user_id = self._resolve_owner_user_id(successor)
                successor.waiting_on_type = None
                successor.waiting_on_user_id = None
                successor.waiting_since = None
                successor.blocker_reason = None
                successor.normalized_status = GlobalStatus.IN_PROGRESS
                successor.normalized_health = GlobalHealth.ON_TRACK

                self._recalculate_successor_chain(successor)
            else:
                successor.waiting_on_type = successor.waiting_on_type or WaitingOnType.DEPENDENCY
                successor.waiting_since = successor.waiting_since or datetime.utcnow()
                successor.normalized_status = GlobalStatus.BLOCKED_DEPENDENCY
                successor.normalized_health = GlobalHealth.AT_RISK

    def _recalculate_successor_chain(self, step: WorkflowStep, visited: set[str] | None = None) -> None:
        visited = visited or set()
        if step.id in visited:
            return
        visited.add(step.id)

        successors = self.db.scalars(
            select(WorkflowStep)
            .join(WorkflowStepDependency, WorkflowStepDependency.successor_step_id == WorkflowStep.id)
            .where(WorkflowStepDependency.predecessor_step_id == step.id)
        ).all()

        for successor in successors:
            if successor.actual_done is not None:
                continue

            predecessors = self.db.scalars(
                select(WorkflowStep)
                .join(WorkflowStepDependency, WorkflowStepDependency.predecessor_step_id == WorkflowStep.id)
                .where(WorkflowStepDependency.successor_step_id == successor.id)
            ).all()
            latest_start = max(
                [
                    (p.actual_done.date() if p.actual_done else p.current_due)
                    for p in predecessors
                    if (p.actual_done is not None or p.current_due is not None)
                ]
                or [successor.current_start or datetime.utcnow().date()]
            )
            successor.current_start = self.timeline.calendar.next_working_day_on_or_after(latest_start)
            successor.current_due = self.timeline.calendar.next_working_day_on_or_after(
                self.timeline.calendar.add_working_days(
                    successor.current_start,
                    self._duration_working_days(successor),
                )
            )
            self._recalculate_successor_chain(successor, visited)

    def _all_predecessors_done(self, step_id: str) -> bool:
        predecessors = self.db.scalars(
            select(WorkflowStep)
            .join(WorkflowStepDependency, WorkflowStepDependency.predecessor_step_id == WorkflowStep.id)
            .where(WorkflowStepDependency.successor_step_id == step_id)
        ).all()
        if not predecessors:
            return True
        return all(p.actual_done is not None for p in predecessors)

    def _duration_working_days(self, step: WorkflowStep) -> int:
        if step.baseline_start and step.baseline_due:
            days = self.timeline.working_days_between(step.baseline_start, step.baseline_due)
            return max(days, 1)
        return 1

    def _resolve_owner_user_id(self, step: WorkflowStep) -> str | None:
        effort_rows = self.db.scalars(
            select(WorkflowStepEffort).where(WorkflowStepEffort.workflow_step_id == step.id)
        ).all()
        assigned_hours_by_user: dict[str, float] = {}
        for effort in effort_rows:
            if not effort.assigned_user_id:
                continue
            assigned_hours_by_user[effort.assigned_user_id] = (
                assigned_hours_by_user.get(effort.assigned_user_id, 0.0) + float(effort.hours or 0.0)
            )
        if len(assigned_hours_by_user) == 1:
            return next(iter(assigned_hours_by_user.keys()))
        if assigned_hours_by_user:
            ranked = sorted(assigned_hours_by_user.items(), key=lambda item: (-item[1], item[0]))
            return ranked[0][0]
        campaign_id: str | None = step.campaign_id
        linked_deliverable_id = step.linked_deliverable_id
        if not campaign_id and linked_deliverable_id:
            deliverable = self.db.get(Deliverable, linked_deliverable_id)
            if deliverable:
                campaign_id = deliverable.campaign_id
        if not campaign_id:
            return None
        assignment = self.db.scalar(
            select(CampaignAssignment).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.role_name == step.owner_role,
            )
        )
        return assignment.user_id if assignment else None

    def _refresh_stage_from_steps(self, stage_id: str | None) -> None:
        if not stage_id:
            return
        stage = self.db.get(Stage, stage_id)
        if not stage:
            return
        steps = self.db.scalars(select(WorkflowStep).where(WorkflowStep.stage_id == stage_id)).all()
        if not steps:
            stage.status = GlobalStatus.NOT_STARTED
            stage.health = GlobalHealth.NOT_STARTED
            stage.baseline_start = None
            stage.baseline_due = None
            stage.current_start = None
            stage.current_due = None
            stage.actual_done = None
            return
        baseline_starts = [s.baseline_start or s.baseline_due for s in steps if (s.baseline_start or s.baseline_due)]
        baseline_dues = [s.baseline_due or s.baseline_start for s in steps if (s.baseline_due or s.baseline_start)]
        current_starts = [s.current_start or s.current_due for s in steps if (s.current_start or s.current_due)]
        current_dues = [s.current_due or s.current_start for s in steps if (s.current_due or s.current_start)]

        stage.baseline_start = min(baseline_starts, default=None)
        stage.baseline_due = max(baseline_dues, default=None)
        stage.current_start = min(current_starts, default=None)
        stage.current_due = max(current_dues, default=None)
        if all(s.actual_done is not None for s in steps):
            stage.actual_done = max((s.actual_done for s in steps if s.actual_done), default=None)
        else:
            stage.actual_done = None

        statuses = [s.normalized_status.value for s in steps if s.normalized_status]
        if statuses and all(v == "done" for v in statuses):
            stage.status = GlobalStatus.DONE
        elif any(v == "blocked_dependency" for v in statuses):
            stage.status = GlobalStatus.BLOCKED_DEPENDENCY
        elif any(v == "blocked_client" for v in statuses):
            stage.status = GlobalStatus.BLOCKED_CLIENT
        elif any(v == "blocked_internal" for v in statuses):
            stage.status = GlobalStatus.BLOCKED_INTERNAL
        elif any(v == "in_progress" for v in statuses):
            stage.status = GlobalStatus.IN_PROGRESS
        elif any(v == "on_hold" for v in statuses):
            stage.status = GlobalStatus.ON_HOLD
        elif statuses and all(v == "cancelled" for v in statuses):
            stage.status = GlobalStatus.CANCELLED
        else:
            stage.status = GlobalStatus.NOT_STARTED

        healths = [s.normalized_health.value for s in steps if s.normalized_health]
        if any(v == "off_track" for v in healths):
            stage.health = GlobalHealth.OFF_TRACK
        elif any(v == "at_risk" for v in healths):
            stage.health = GlobalHealth.AT_RISK
        elif any(v == "on_track" for v in healths):
            stage.health = GlobalHealth.ON_TRACK
        else:
            stage.health = GlobalHealth.NOT_STARTED
