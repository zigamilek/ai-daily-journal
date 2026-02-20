from __future__ import annotations

from datetime import datetime, timezone

from ai_daily_journal.services.date_resolution import resolve_target_date


def test_resolve_danes() -> None:
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    resolved = resolve_target_date("Danes sem šel na sprehod", now, "Europe/Ljubljana")
    assert resolved.isoformat() == "2026-02-20"


def test_resolve_vceraj() -> None:
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    resolved = resolve_target_date("Včeraj sem imel sestanek", now, "Europe/Ljubljana")
    assert resolved.isoformat() == "2026-02-19"


def test_resolve_v_torek_most_recent_before_today() -> None:
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)  # Friday
    resolved = resolve_target_date("V torek sem zaključil nalogo", now, "Europe/Ljubljana")
    assert resolved.isoformat() == "2026-02-17"


def test_resolve_prejsnji_ponedeljek() -> None:
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)  # Friday
    resolved = resolve_target_date("Prejšnji ponedeljek sem bil doma", now, "Europe/Ljubljana")
    assert resolved.isoformat() == "2026-02-09"
