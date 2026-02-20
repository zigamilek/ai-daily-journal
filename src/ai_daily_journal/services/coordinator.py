from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Callable

from pydantic import ValidationError

from ai_daily_journal.schemas.coordinator import Action, CoordinatorDecision


class CoordinatorOutputError(RuntimeError):
    pass


@dataclass(slots=True)
class CoordinatorContext:
    resolved_date: date
    user_text: str
    candidate_entry_ids: list[int]
    top_similarity: float
    existing_entries_count: int


Responder = Callable[[CoordinatorContext], str]


@dataclass(slots=True)
class CoordinatorResult:
    decision: CoordinatorDecision
    warnings: list[str]
    attempts: int


class CoordinatorService:
    def __init__(
        self,
        max_retries: int,
        responder: Responder | None = None,
        *,
        allow_fallback: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.responder = responder
        self.allow_fallback = allow_fallback

    def decide(self, context: CoordinatorContext) -> CoordinatorResult:
        errors: list[str] = []
        attempts = 0
        if self.responder is not None:
            for _ in range(self.max_retries + 1):
                attempts += 1
                raw = self.responder(context)
                try:
                    data = json.loads(raw)
                    decision = CoordinatorDecision.model_validate(data)
                    return CoordinatorResult(decision=decision, warnings=[], attempts=attempts)
                except (json.JSONDecodeError, ValidationError) as exc:
                    errors.append(str(exc))
                    continue
        if self.allow_fallback:
            fallback = CoordinatorDecision.model_validate(json.loads(self._local_responder(context)))
            warning = (
                "Coordinator model output was invalid or unavailable; "
                "used deterministic fallback with explicit warning."
            )
            if errors:
                warning += f" Last error: {errors[-1]}"
            return CoordinatorResult(decision=fallback, warnings=[warning], attempts=max(attempts, 1))
        raise CoordinatorOutputError(
            "Coordinator did not return valid JSON after retries. "
            f"Last errors: {errors[-1] if errors else 'unknown'}"
        )

    def _local_responder(self, ctx: CoordinatorContext) -> str:
        if ctx.top_similarity >= 0.96:
            action = Action.noop
            reason = "Vnos je skoraj enak obstoječemu dogodku."
        elif ctx.top_similarity >= 0.88 and ctx.candidate_entry_ids:
            action = Action.update
            reason = "Vnos je podoben obstoječemu dogodku in ga je smiselno posodobiti."
        elif ctx.existing_entries_count > 0:
            action = Action.append
            reason = "Dan že vsebuje vnose; dodamo nov dogodek."
        else:
            action = Action.create
            reason = "Za ta dan še ni vnosa; ustvarimo nov zapis."

        return json.dumps(
            {
                "resolved_date": ctx.resolved_date.isoformat(),
                "action": action.value,
                "candidate_entry_ids": ctx.candidate_entry_ids,
                "reason": reason,
            },
            ensure_ascii=False,
        )
