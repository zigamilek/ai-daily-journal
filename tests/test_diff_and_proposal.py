from __future__ import annotations

from datetime import date

from ai_daily_journal.db.models import JournalDay, JournalEntry
from ai_daily_journal.services.diffing import generate_unified_diff
from ai_daily_journal.services.write_flow import JournalWriteService


def test_unified_diff_generation() -> None:
    current = "# Dnevnik 2026-02-20\n\n1. Tekel sem.\n"
    proposed = "# Dnevnik 2026-02-20\n\n1. Tekel sem.\n2. Bral sem knjigo.\n"
    diff = generate_unified_diff(current, proposed, file_label="2026-02-20.md")
    assert "--- a/2026-02-20.md" in diff
    assert "+++ b/2026-02-20.md" in diff
    assert "+2. Bral sem knjigo." in diff


def test_proposal_contains_diff_before_confirm(db_session, test_config, test_user):
    day = JournalDay(user_id=test_user.id, day_date=date(2026, 2, 20), timezone="Europe/Ljubljana")
    db_session.add(day)
    db_session.flush()
    db_session.add(
        JournalEntry(
            day_id=day.id,
            sequence_no=1,
            event_text_sl="Tekel sem zjutraj.",
            source_user_text="tekel sem",
            event_hash="abc",
        )
    )
    db_session.commit()

    service = JournalWriteService(db_session, test_config)
    result = service.propose(
        user_id=test_user.id,
        source_text="Danes sem bral knjigo",
        session_id=None,
        instruction=None,
    )
    assert "diff_text" in result
    assert result["session_id"] is not None
    assert "Dnevnik 2026-02-20" in result["diff_text"]
