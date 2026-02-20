from __future__ import annotations

import json
from datetime import date

import pytest

from ai_daily_journal.services.coordinator import (
    CoordinatorContext,
    CoordinatorOutputError,
    CoordinatorService,
)


def test_coordinator_retries_until_valid_json() -> None:
    attempts = {"count": 0}

    def responder(_ctx: CoordinatorContext) -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return "not-json"
        return json.dumps(
            {
                "resolved_date": "2026-02-20",
                "action": "append",
                "candidate_entry_ids": [],
                "reason": "Dodamo nov vnos.",
            }
        )

    service = CoordinatorService(max_retries=3, responder=responder, allow_fallback=False)
    result = service.decide(
        CoordinatorContext(
            resolved_date=date(2026, 2, 20),
            user_text="Danes sem tekel",
            candidate_entry_ids=[],
            top_similarity=0.1,
            existing_entries_count=1,
        )
    )
    assert attempts["count"] == 3
    assert result.decision.action.value == "append"
    assert result.warnings == []


def test_coordinator_raises_when_invalid_and_fallback_disabled() -> None:
    def responder(_ctx: CoordinatorContext) -> str:
        return '{"resolved_date":"bad"}'

    service = CoordinatorService(max_retries=1, responder=responder, allow_fallback=False)
    with pytest.raises(CoordinatorOutputError):
        service.decide(
            CoordinatorContext(
                resolved_date=date(2026, 2, 20),
                user_text="Danes",
                candidate_entry_ids=[],
                top_similarity=0.0,
                existing_entries_count=0,
            )
        )


def test_coordinator_explicit_warning_on_fallback() -> None:
    service = CoordinatorService(max_retries=1, responder=None, allow_fallback=True)
    result = service.decide(
        CoordinatorContext(
            resolved_date=date(2026, 2, 20),
            user_text="Danes",
            candidate_entry_ids=[],
            top_similarity=0.0,
            existing_entries_count=0,
        )
    )
    assert result.warnings
    assert "fallback" in result.warnings[0]
