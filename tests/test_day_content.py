from __future__ import annotations

from datetime import date

from ai_daily_journal.services.day_content import parse_day_edit_text, render_day_text


def test_day_text_render_is_deterministic() -> None:
    day = date(2026, 2, 20)
    events = ["Tekel sem.", "Bral sem."]
    one = render_day_text(day, events)
    two = render_day_text(day, events)
    assert one == two
    assert one.startswith("Dnevnik za 2026-02-20")


def test_parse_day_edit_text_supports_numbered_input() -> None:
    parsed = parse_day_edit_text(
        """
        Dnevnik za 2026-02-20

        1. Prvi vnos
        2. Drugi vnos

        Tretji brez številke
        """.strip()
    )
    assert parsed == ["Prvi vnos", "Drugi vnos", "Tretji brez številke"]
