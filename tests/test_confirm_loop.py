from __future__ import annotations

from sqlalchemy import select

from ai_daily_journal.db.models import WriteOperation, WriteSession
from ai_daily_journal.services.write_flow import JournalWriteService


def test_iterative_revision_then_confirm(db_session, test_config, test_user):
    service = JournalWriteService(db_session, test_config)
    first = service.propose(
        user_id=test_user.id,
        source_text="Danes sem programiral cel dan",
        session_id=None,
        instruction=None,
    )
    session_id = int(first["session_id"])

    revised = service.propose(
        user_id=test_user.id,
        source_text="Danes sem programiral cel dan",
        session_id=session_id,
        instruction="bolj jedrnato",
    )
    assert revised["session_id"] == session_id
    assert revised["operation_id"] != first["operation_id"]

    confirmed = service.confirm(user_id=test_user.id, session_id=session_id, idempotency_key="abc123456")
    assert confirmed["status"] == "ok"
    assert "Dnevnik" in confirmed["final_content"]

    session = db_session.execute(select(WriteSession).where(WriteSession.id == session_id)).scalar_one()
    assert session.status.value == "confirmed"

    operation_count = len(
        db_session.execute(
            select(WriteOperation).where(WriteOperation.session_id == session_id)
        ).scalars().all()
    )
    assert operation_count == 2
