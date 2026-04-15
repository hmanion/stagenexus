from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.domain import RoleName
from app.services.ops_defaults_service import OpsDefaultsService


DEFAULT_WEEKLY_CAPACITY = {
    RoleName.CC: 16.0,
    RoleName.CM: 28.0,
    RoleName.AM: 8.0,
    RoleName.DN: 16.0,
    RoleName.MM: 16.0,
    RoleName.CCS: 16.0,
}


@dataclass
class CapacityEvaluation:
    capacity_hours: float
    planned_hours: float
    is_over_capacity: bool


class CapacityService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self._cached_defaults: dict | None = None

    def _capacity_map(self) -> dict[RoleName, float]:
        mapping = dict(DEFAULT_WEEKLY_CAPACITY)
        if not self.db:
            return mapping
        if self._cached_defaults is None:
            self._cached_defaults = OpsDefaultsService(self.db).get()
        configured = (self._cached_defaults.get("capacity_hours_per_week") or {})
        mapping[RoleName.AM] = float(configured.get("am", mapping[RoleName.AM]))
        mapping[RoleName.CM] = float(configured.get("cm", mapping[RoleName.CM]))
        mapping[RoleName.CC] = float(configured.get("cc", mapping[RoleName.CC]))
        mapping[RoleName.CCS] = float(configured.get("cc", mapping[RoleName.CCS]))
        mapping[RoleName.DN] = float(configured.get("dn", mapping[RoleName.DN]))
        mapping[RoleName.MM] = float(configured.get("mm", mapping[RoleName.MM]))
        return mapping

    def evaluate(self, role_name: RoleName, planned_hours: float) -> CapacityEvaluation:
        cap = self._capacity_map().get(role_name, 40.0)
        return CapacityEvaluation(capacity_hours=cap, planned_hours=planned_hours, is_over_capacity=planned_hours > cap)
