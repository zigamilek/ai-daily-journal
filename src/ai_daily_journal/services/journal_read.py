from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily_journal.db.models import JournalDay, JournalEntry
from ai_daily_journal.services.day_content import render_day_text


class JournalReadService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def latest_day(self, user_id: int) -> JournalDay | None:
        return self.db.execute(
            select(JournalDay)
            .where(JournalDay.user_id == user_id)
            .order_by(JournalDay.day_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def tree(self, user_id: int) -> list[dict[str, object]]:
        days = self.db.execute(
            select(JournalDay.day_date).where(JournalDay.user_id == user_id).order_by(JournalDay.day_date.desc())
        ).scalars()
        grouped: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
        for d in days:
            grouped[d.year][d.month].append(d.isoformat())
        output: list[dict[str, object]] = []
        for year in sorted(grouped.keys(), reverse=True):
            months = []
            for month in sorted(grouped[year].keys(), reverse=True):
                months.append({"month": month, "days": grouped[year][month]})
            output.append({"year": year, "months": months})
        return output

    def render_day_content(self, user_id: int, day_date: str) -> str | None:
        parsed = date.fromisoformat(day_date)
        day = self.db.execute(
            select(JournalDay).where(JournalDay.user_id == user_id, JournalDay.day_date == parsed)
        ).scalar_one_or_none()
        if day is None:
            return None
        entries = self.db.execute(
            select(JournalEntry)
            .where(JournalEntry.day_id == day.id, JournalEntry.superseded_by_entry_id.is_(None))
            .order_by(JournalEntry.sequence_no.asc())
        ).scalars()
        return render_day_text(day.day_date, [entry.event_text_sl for entry in entries])
