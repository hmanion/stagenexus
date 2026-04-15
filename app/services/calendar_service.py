from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
import json
import ssl
import urllib.request

import certifi

from app.core.config import settings


DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


@dataclass
class WorkingCalendar:
    working_days: set[int]
    holidays: set[date]

    def is_working_day(self, d: date) -> bool:
        return d.weekday() in self.working_days and d not in self.holidays

    def add_working_days(self, start: date, days: int) -> date:
        if days < 0:
            raise ValueError("days must be >= 0")

        current = start
        added = 0
        while added < days:
            current += timedelta(days=1)
            if self.is_working_day(current):
                added += 1
        return current

    def next_working_day_on_or_after(self, d: date) -> date:
        current = d
        while not self.is_working_day(current):
            current += timedelta(days=1)
        return current


class HolidayProvider:
    def __init__(self, source_url: str | None = None) -> None:
        self.source_url = source_url or settings.holiday_source_url

    def fetch_england_wales_holidays(self) -> set[date]:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(self.source_url, timeout=10, context=ssl_ctx) as response:
            payload = json.loads(response.read().decode("utf-8"))

        events = payload.get("england-and-wales", {}).get("events", [])
        result = set()
        for event in events:
            event_date = event.get("date")
            if event_date:
                result.add(date.fromisoformat(event_date))
        return result


def build_calendar(holiday_dates: set[date] | None = None) -> WorkingCalendar:
    holiday_dates = holiday_dates or set()
    working_days = {DAY_INDEX[d] for d in settings.working_week if d in DAY_INDEX}
    return WorkingCalendar(working_days=working_days, holidays=holiday_dates)


def safe_fetch_england_wales_holidays() -> set[date]:
    try:
        return HolidayProvider().fetch_england_wales_holidays()
    except Exception:
        return set()


@lru_cache(maxsize=1)
def holiday_snapshot() -> tuple[date, ...]:
    return tuple(sorted(safe_fetch_england_wales_holidays()))


def build_default_working_calendar() -> WorkingCalendar:
    return build_calendar(set(holiday_snapshot()))
