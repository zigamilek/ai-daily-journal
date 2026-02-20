from __future__ import annotations

import pytest

from ai_daily_journal.services.write_flow import JournalWriteService


def test_idempotency_replay_returns_same_operation(db_session, test_config, test_user):
    service = JournalWriteService(db_session, test_config)
    proposal = service.propose(
        user_id=test_user.id,
        source_text="Danes sem šel na kolo",
        session_id=None,
        instruction=None,
    )
    first = service.confirm(
        user_id=test_user.id,
        session_id=int(proposal["session_id"]),
        idempotency_key="idem-key-123",
    )
    second = service.confirm(
        user_id=test_user.id,
        session_id=int(proposal["session_id"]),
        idempotency_key="idem-key-123",
    )
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert first["operation_id"] == second["operation_id"]


def test_idempotency_key_reuse_with_different_request_fails(db_session, test_config, test_user):
    service = JournalWriteService(db_session, test_config)
    proposal = service.propose(
        user_id=test_user.id,
        source_text="Danes sem kuhal",
        session_id=None,
        instruction=None,
    )
    session_id = int(proposal["session_id"])
    service.confirm(user_id=test_user.id, session_id=session_id, idempotency_key="dup-key-456")

    next_proposal = service.propose(
        user_id=test_user.id,
        source_text="Danes sem tekel",
        session_id=None,
        instruction=None,
    )
    with pytest.raises(ValueError):
        service.confirm(
            user_id=test_user.id,
            session_id=int(next_proposal["session_id"]),
            idempotency_key="dup-key-456",
        )
