from __future__ import annotations

from datetime import date
from pathlib import Path

from ai_daily_journal.services.projection_renderer import (
    projection_file_path,
    render_day_markdown,
    write_projection_atomic,
)


def test_projection_render_is_deterministic() -> None:
    day = date(2026, 2, 20)
    events = ["Tekel sem.", "Bral sem."]
    one = render_day_markdown(day, events)
    two = render_day_markdown(day, events)
    assert one == two
    assert one.startswith("# Dnevnik 2026-02-20")


def test_projection_atomic_write_consistency(tmp_path: Path) -> None:
    day = date(2026, 2, 20)
    content = render_day_markdown(day, ["Prvi vnos."])
    target = write_projection_atomic(tmp_path, day, content)
    assert target == projection_file_path(tmp_path, day)
    assert target.read_text(encoding="utf-8") == content

    updated = render_day_markdown(day, ["Prvi vnos.", "Drugi vnos."])
    write_projection_atomic(tmp_path, day, updated)
    assert target.read_text(encoding="utf-8") == updated
