from __future__ import annotations

from app.services.calendar_service import HolidayProvider


def main() -> None:
    provider = HolidayProvider()
    holidays = sorted(provider.fetch_england_wales_holidays())
    print(f"Fetched {len(holidays)} England/Wales holidays")
    for d in holidays[:20]:
        print(d.isoformat())


if __name__ == "__main__":
    main()
