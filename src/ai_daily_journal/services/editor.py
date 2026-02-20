from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ai_daily_journal.schemas.coordinator import Action


@dataclass(slots=True)
class EditorContext:
    action: Action
    source_text: str
    instruction: str | None
    existing_entries: list[dict]
    candidate_entry_ids: list[int]


@dataclass(slots=True)
class EditorResult:
    entries: list[dict]
    warnings: list[str]


TextResponder = Callable[[str, str | None], str]


class EditorService:
    """Deterministic Slovenian event text proposal service."""

    def __init__(self, responder: TextResponder | None = None) -> None:
        self.responder = responder

    def propose(self, ctx: EditorContext) -> EditorResult:
        warnings: list[str] = []
        polished = self._polish_slovenian(ctx.source_text, ctx.instruction)
        if self.responder is None:
            warnings.append("Editor model unavailable; deterministic Slovenian fallback used.")
        else:
            try:
                polished = self.responder(ctx.source_text, ctx.instruction)
            except Exception as exc:  # noqa: BLE001
                warnings.append(
                    "Editor model failed; used deterministic Slovenian text fallback. "
                    f"Reason: {exc}"
                )
        entries = [dict(item) for item in ctx.existing_entries]

        if ctx.action == Action.noop:
            return EditorResult(entries=entries, warnings=warnings)

        if ctx.action == Action.create:
            return EditorResult(
                entries=[
                    {
                        "sequence_no": 1,
                        "event_text_sl": polished,
                        "source_user_text": ctx.source_text,
                        "updated_from_entry_id": None,
                    }
                ],
                warnings=warnings,
            )

        if ctx.action == Action.append:
            entries.append(
                {
                    "sequence_no": len(entries) + 1,
                    "event_text_sl": polished,
                    "source_user_text": ctx.source_text,
                    "updated_from_entry_id": None,
                }
            )
            return EditorResult(entries=entries, warnings=warnings)

        # update path
        if not entries:
            return EditorResult(
                entries=[
                    {
                        "sequence_no": 1,
                        "event_text_sl": polished,
                        "source_user_text": ctx.source_text,
                        "updated_from_entry_id": None,
                    }
                ],
                warnings=warnings,
            )

        target_id = ctx.candidate_entry_ids[0] if ctx.candidate_entry_ids else entries[-1]["id"]
        updated = []
        for item in entries:
            if item["id"] == target_id:
                updated.append(
                    {
                        "id": item["id"],
                        "sequence_no": item["sequence_no"],
                        "event_text_sl": polished,
                        "source_user_text": ctx.source_text,
                        "updated_from_entry_id": item["id"],
                    }
                )
            else:
                updated.append(item)
        return EditorResult(entries=updated, warnings=warnings)

    def _polish_slovenian(self, source_text: str, instruction: str | None) -> str:
        text = source_text.strip()
        if instruction:
            text = f"{text} ({instruction.strip()})"
        if not text.endswith("."):
            text += "."
        return text[0].upper() + text[1:]
