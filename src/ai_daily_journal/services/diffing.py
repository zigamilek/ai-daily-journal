from __future__ import annotations

from difflib import unified_diff


def generate_unified_diff(current: str, proposed: str, *, file_label: str) -> str:
    current_lines = current.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)
    diff = unified_diff(
        current_lines,
        proposed_lines,
        fromfile=f"a/{file_label}",
        tofile=f"b/{file_label}",
        lineterm="",
    )
    out = "\n".join(diff)
    return out or "(no diff)"
