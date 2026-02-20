from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


SLO_WEEKDAYS = {
    "ponedeljek": 0,
    "torek": 1,
    "sreda": 2,
    "četrtek": 3,
    "petek": 4,
    "sobota": 5,
    "nedelja": 6,
}


def _most_recent_weekday(base: date, weekday: int, *, include_today: bool) -> date:
    delta = (base.weekday() - weekday) % 7
    if delta == 0 and not include_today:
        delta = 7
    return base - timedelta(days=delta)


def resolve_target_date(user_text: str, now: datetime, timezone_name: str) -> date:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    today = local_now.date()
    normalized = user_text.casefold()

    if "danes" in normalized:
        return today
    if "včeraj" in normalized or "vceraj" in normalized:
        return today - timedelta(days=1)

    for weekday_name, weekday_no in SLO_WEEKDAYS.items():
        if f"v {weekday_name}" in normalized:
            return _most_recent_weekday(today, weekday_no, include_today=False)

    if "prejšnji ponedeljek" in normalized or "prejsnji ponedeljek" in normalized:
        recent_monday = _most_recent_weekday(today, SLO_WEEKDAYS["ponedeljek"], include_today=True)
        return recent_monday - timedelta(days=7)

    return today
