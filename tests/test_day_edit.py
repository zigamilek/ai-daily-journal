from __future__ import annotations

from datetime import date

from sqlalchemy import select

from ai_daily_journal.db.models import JournalDay, JournalEntry
from ai_daily_journal.services.write_flow import JournalWriteService


def test_day_edit_replaces_day_content(db_session, test_config, test_user):
    day = JournalDay(user_id=test_user.id, day_date=date(2026, 2, 20), timezone="Europe/Ljubljana")
    db_session.add(day)
    db_session.flush()
    db_session.add_all(
        [
            JournalEntry(
                day_id=day.id,
                sequence_no=1,
                event_text_sl="Tekel sem zjutraj.",
                source_user_text="Tekel sem zjutraj.",
                event_hash="h1",
            ),
            JournalEntry(
                day_id=day.id,
                sequence_no=2,
                event_text_sl="Popoldne sem bral.",
                source_user_text="Popoldne sem bral.",
                event_hash="h2",
            ),
        ]
    )
    db_session.commit()

    service = JournalWriteService(db_session, test_config)
    proposal = service.propose_day_edit(
        user_id=test_user.id,
        day_date="2026-02-20",
        edited_content="Dnevnik za 2026-02-20\n\n1. Tekel sem in nato počival.",
        session_id=None,
    )
    assert proposal["action"] == "update"

    confirmed = service.confirm(
        user_id=test_user.id,
        session_id=int(proposal["session_id"]),
        idempotency_key="day-edit-key-001",
    )
    assert confirmed["status"] == "ok"
    assert "Tekel sem in nato počival." in confirmed["final_content"]
    assert "Popoldne sem bral." not in confirmed["final_content"]

    active_entries = list(
        db_session.execute(
            select(JournalEntry)
            .where(JournalEntry.day_id == day.id, JournalEntry.superseded_by_entry_id.is_(None))
            .order_by(JournalEntry.sequence_no.asc())
        ).scalars()
    )
    assert [entry.event_text_sl for entry in active_entries] == ["Tekel sem in nato počival."]
