from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path


def render_day_markdown(day_date: date, events: list[str]) -> str:
    header = f"# Dnevnik {day_date.isoformat()}\n\n"
    if not events:
        return header + "_Brez vnosov._\n"
    body = "\n".join([f"{idx}. {event.strip()}" for idx, event in enumerate(events, start=1)])
    return header + body + "\n"


def projection_file_path(root: Path, day_date: date) -> Path:
    return root / f"{day_date.isoformat()}.md"


def write_projection_atomic(root: Path, day_date: date, content: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = projection_file_path(root, day_date)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=root, encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, target)
    return target
