from __future__ import annotations

from datetime import date

from ai_daily_journal.db.models import JournalDay, JournalEntry
from ai_daily_journal.schemas.coordinator import Action, CoordinatorDecision
from ai_daily_journal.services.coordinator import CoordinatorResult
from ai_daily_journal.services.semantic_search import SemanticCandidate
from ai_daily_journal.services.write_flow import JournalWriteService


def seed_day_entry(db_session, user_id: int):
    day = JournalDay(user_id=user_id, day_date=date(2026, 2, 20), timezone="Europe/Ljubljana")
    db_session.add(day)
    db_session.flush()
    entry = JournalEntry(
        day_id=day.id,
        sequence_no=1,
        event_text_sl="Tekel sem 5 km.",
        source_user_text="tekel sem 5 km",
        event_hash="x1",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return day, entry


def test_semantic_high_similarity_forces_noop(db_session, test_config, test_user):
    day, entry = seed_day_entry(db_session, test_user.id)
    service = JournalWriteService(db_session, test_config)
    service.semantic.search_same_day_candidates = lambda *_args, **_kwargs: [
        SemanticCandidate(entry_id=entry.id, similarity=0.99, event_text_sl=entry.event_text_sl)
    ]
    service.coordinator.decide = lambda _ctx: CoordinatorResult(
        decision=CoordinatorDecision(
            resolved_date=day.day_date,
            action=Action.append,
            candidate_entry_ids=[entry.id],
            reason="Model action",
        ),
        warnings=[],
        attempts=1,
    )
    result = service.propose(user_id=test_user.id, source_text="Danes sem tekel 5 km", session_id=None, instruction=None)
    assert result["action"] == "noop"


def test_semantic_medium_similarity_forces_update(db_session, test_config, test_user):
    day, entry = seed_day_entry(db_session, test_user.id)
    service = JournalWriteService(db_session, test_config)
    service.semantic.search_same_day_candidates = lambda *_args, **_kwargs: [
        SemanticCandidate(entry_id=entry.id, similarity=0.90, event_text_sl=entry.event_text_sl)
    ]
    service.coordinator.decide = lambda _ctx: CoordinatorResult(
        decision=CoordinatorDecision(
            resolved_date=day.day_date,
            action=Action.append,
            candidate_entry_ids=[entry.id],
            reason="Model action",
        ),
        warnings=[],
        attempts=1,
    )
    result = service.propose(user_id=test_user.id, source_text="Danes sem tekel", session_id=None, instruction=None)
    assert result["action"] == "update"


def test_semantic_low_similarity_uses_append(db_session, test_config, test_user):
    seed_day_entry(db_session, test_user.id)
    service = JournalWriteService(db_session, test_config)
    service.semantic.search_same_day_candidates = lambda *_args, **_kwargs: [
        SemanticCandidate(entry_id=999, similarity=0.20, event_text_sl="Drugo")
    ]
    result = service.propose(
        user_id=test_user.id,
        source_text="Danes sem kuhal večerjo",
        session_id=None,
        instruction=None,
    )
    assert result["action"] == "append"
