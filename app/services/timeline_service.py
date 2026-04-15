from __future__ import annotations

from datetime import date

from app.services.calendar_service import WorkingCalendar


class TimelineService:
    def __init__(self, calendar: WorkingCalendar) -> None:
        self.calendar = calendar

    def plan_step_window(self, start_date: date, duration_working_days: int) -> tuple[date, date]:
        if duration_working_days < 0:
            raise ValueError("duration must be >= 0")
        due = self.calendar.add_working_days(start_date, duration_working_days)
        return start_date, due

    def variance_working_days(self, baseline_due: date, current_due: date) -> int:
        if current_due == baseline_due:
            return 0

        if current_due > baseline_due:
            cursor = baseline_due
            count = 0
            while cursor < current_due:
                cursor = date.fromordinal(cursor.toordinal() + 1)
                if self.calendar.is_working_day(cursor):
                    count += 1
            return count

        cursor = current_due
        count = 0
        while cursor < baseline_due:
            cursor = date.fromordinal(cursor.toordinal() + 1)
            if self.calendar.is_working_day(cursor):
                count += 1
        return -count

    def working_days_between(self, start: date, end: date) -> int:
        if start == end:
            return 0
        if end < start:
            return -self.working_days_between(end, start)

        cursor = start
        count = 0
        while cursor < end:
            cursor = date.fromordinal(cursor.toordinal() + 1)
            if self.calendar.is_working_day(cursor):
                count += 1
        return count
