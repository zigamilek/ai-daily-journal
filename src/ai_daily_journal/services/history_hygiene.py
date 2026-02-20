from __future__ import annotations

import re

_WRAPPER_BLOCK_RE = re.compile(
    r"<(system_reminder|user_info|open_and_recently_viewed_files|attached_files|code_selection)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_model_text(text: str) -> str:
    cleaned = _WRAPPER_BLOCK_RE.sub("", text)
    cleaned = re.sub(r"\s{3,}", "\n\n", cleaned)
    return cleaned.strip()
