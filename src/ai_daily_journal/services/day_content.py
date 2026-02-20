from __future__ import annotations

from datetime import date


def render_day_text(day_date: date, events: list[str]) -> str:
    header = f"Dnevnik za {day_date.isoformat()}\n\n"
    if not events:
        return header + "Brez vnosov.\n"
    lines = [f"{idx}. {event.strip()}" for idx, event in enumerate(events, start=1)]
    return header + "\n".join(lines) + "\n"


def parse_day_edit_text(content: str) -> list[str]:
    lines: list[str] = []
    for raw in content.splitlines():
        value = raw.strip()
        if not value:
            continue
        lowered = value.casefold()
        if lowered.startswith("dnevnik za "):
            continue
        if lowered in {"brez vnosov.", "brez vnosov"}:
            continue
        if "." in value:
            head, tail = value.split(".", 1)
            if head.isdigit() and tail.strip():
                value = tail.strip()
        lines.append(value)
    return lines
