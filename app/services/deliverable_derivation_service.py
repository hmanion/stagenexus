from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Deliverable, DeliverableStage, WorkflowStep


class DeliverableDerivationService:
    def __init__(self, db: Session):
        self.db = db

    def assign_sequence_and_title(self, deliverable: Deliverable) -> Deliverable:
        if not deliverable.campaign_id:
            if not deliverable.sequence_number or deliverable.sequence_number < 1:
                deliverable.sequence_number = 1
            return deliverable
        rows = self.db.scalars(
            select(Deliverable).where(
                Deliverable.campaign_id == deliverable.campaign_id,
                Deliverable.deliverable_type == deliverable.deliverable_type,
            )
        ).all()
        if deliverable.id:
            rows = [r for r in rows if r.id != deliverable.id]
        max_seq = max([int(r.sequence_number or 0) for r in rows], default=0)
        deliverable.sequence_number = max(max_seq + 1, 1)
        base = str(deliverable.deliverable_type.value if hasattr(deliverable.deliverable_type, "value") else deliverable.deliverable_type)
        label = base.replace("_", " ").title()
        deliverable.title = f"{label} {deliverable.sequence_number}"
        return deliverable

    def recompute_operational_stage_status(self, deliverable: Deliverable) -> Deliverable:
        stage = self.derive_operational_stage_status(deliverable)
        deliverable.operational_stage_status = stage
        return deliverable

    def derive_operational_stage_status(self, deliverable: Deliverable) -> DeliverableStage:
        if not deliverable.id:
            return DeliverableStage.PLANNING
        steps = self.db.scalars(
            select(WorkflowStep).where(
                WorkflowStep.linked_deliverable_id == deliverable.id,
            )
        ).all()
        in_progress = [
            s for s in steps
            if str((s.normalized_status.value if hasattr(s.normalized_status, "value") else s.normalized_status) or "").lower() == "in_progress"
        ]
        if not in_progress:
            return DeliverableStage.PLANNING
        counts: Counter[str] = Counter(str(s.stage_name or "").strip().lower() for s in in_progress if s.stage_name)
        if not counts:
            return DeliverableStage.PLANNING
        stage_name, _ = counts.most_common(1)[0]
        if stage_name not in {"planning", "production", "promotion", "reporting"}:
            return DeliverableStage.PLANNING
        return DeliverableStage(stage_name)
