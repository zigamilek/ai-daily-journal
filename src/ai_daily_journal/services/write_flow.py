from __future__ import annotations

from datetime import date as date_cls, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily_journal.config.loader import load_secrets, resolve_secret
from ai_daily_journal.config.schema import AppConfig
from ai_daily_journal.db.models import (
    JournalDay,
    JournalEntry,
    OperationAction,
    OperationStatus,
    SessionStatus,
    User,
    WriteOperation,
    WriteSession,
)
from ai_daily_journal.schemas.coordinator import Action
from ai_daily_journal.services.coordinator import CoordinatorContext, CoordinatorService
from ai_daily_journal.services.day_content import parse_day_edit_text, render_day_text
from ai_daily_journal.services.date_resolution import resolve_target_date
from ai_daily_journal.services.diffing import generate_unified_diff
from ai_daily_journal.services.editor import EditorContext, EditorService
from ai_daily_journal.services.history_hygiene import sanitize_model_text
from ai_daily_journal.services.model_client import OpenAICompatibleClient
from ai_daily_journal.services.semantic_search import SemanticSearchService, semantic_relation
from ai_daily_journal.services.write_transaction import WriteTransactionService
from ai_daily_journal.paths import default_env_path


class JournalWriteService:
    def __init__(self, db: Session, config: AppConfig | None) -> None:
        if config is None:
            raise ValueError("Config must be loaded")
        self.db = db
        self.config = config
        env = load_secrets(default_env_path())
        self.model_warnings: list[str] = []

        coordinator_responder = None
        try:
            coordinator_client = OpenAICompatibleClient(
                base_url=config.models.coordinator.base_url,
                api_key=resolve_secret(env, config.models.coordinator.api_key_env),
            )

            def coordinator_responder(ctx: CoordinatorContext) -> str:
                user_prompt = (
                    f"resolved_date_hint={ctx.resolved_date.isoformat()}\n"
                    f"user_text={ctx.user_text}\n"
                    f"candidate_entry_ids={ctx.candidate_entry_ids}\n"
                    f"top_similarity={ctx.top_similarity}\n"
                    f"existing_entries_count={ctx.existing_entries_count}"
                )
                return coordinator_client.chat(
                    model=config.models.coordinator.model_name,
                    system_prompt=(
                        "You are coordinator for AI Daily Journal. "
                        "Return strict JSON only with keys: "
                        "resolved_date (YYYY-MM-DD), action (noop|append|update|create), "
                        "candidate_entry_ids (array of ints), reason (Slovenian)."
                    ),
                    user_prompt=user_prompt,
                    temperature=config.models.coordinator.temperature,
                )
        except Exception as exc:  # noqa: BLE001
            self.model_warnings.append(
                f"Coordinator model unavailable, deterministic fallback active: {exc}"
            )

        editor_responder = None
        try:
            editor_client = OpenAICompatibleClient(
                base_url=config.models.editor.base_url,
                api_key=resolve_secret(env, config.models.editor.api_key_env),
            )

            def editor_responder(source_text: str, instruction: str | None) -> str:
                user_prompt = (
                    f"source_text={source_text}\n"
                    f"instruction={instruction or ''}\n"
                    "Return one polished Slovenian event sentence."
                )
                raw = editor_client.chat(
                    model=config.models.editor.model_name,
                    system_prompt=(
                        "Polish daily journal event in Slovenian. "
                        "Do not invent facts. Return JSON: {\"event_text_sl\":\"...\"}."
                    ),
                    user_prompt=user_prompt,
                    temperature=config.models.editor.temperature,
                )
                import json

                return str(json.loads(raw)["event_text_sl"])
        except Exception as exc:  # noqa: BLE001
            self.model_warnings.append(f"Editor model unavailable, deterministic fallback active: {exc}")

        embeddings_embedder = None
        if config.models.embeddings.enabled:
            try:
                embeddings_client = OpenAICompatibleClient(
                    base_url=config.models.embeddings.base_url,
                    api_key=resolve_secret(env, config.models.embeddings.api_key_env),
                )

                def embeddings_embedder(text: str) -> list[float]:
                    return embeddings_client.embedding(
                        model=config.models.embeddings.model_name,
                        text=text,
                    )
            except Exception as exc:  # noqa: BLE001
                self.model_warnings.append(
                    f"Embeddings model unavailable, deterministic fallback active: {exc}"
                )

        self.coordinator = CoordinatorService(
            max_retries=config.models.coordinator.max_retries,
            responder=coordinator_responder,
            allow_fallback=True,
        )
        self.editor = EditorService(responder=editor_responder)
        self.semantic = SemanticSearchService(
            db,
            embeddings_model_name=config.models.embeddings.model_name,
            dimensions=config.models.embeddings.dimensions,
            embedder=embeddings_embedder,
        )
        self.write_tx = WriteTransactionService(
            db,
            embeddings_model_name=config.models.embeddings.model_name,
            embeddings_dimensions=config.models.embeddings.dimensions,
        )

    def propose(
        self,
        *,
        user_id: int,
        source_text: str,
        session_id: int | None,
        instruction: str | None,
    ) -> dict[str, object]:
        sanitized_text = sanitize_model_text(source_text)
        sanitized_instruction = sanitize_model_text(instruction) if instruction else None
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        now = datetime.now(timezone.utc)
        resolved = resolve_target_date(sanitized_text, now, user.timezone)

        if session_id is None:
            session = WriteSession(user_id=user_id, day_date=resolved, status=SessionStatus.draft)
            self.db.add(session)
            self.db.flush()
        else:
            session = self.db.execute(
                select(WriteSession).where(
                    WriteSession.id == session_id,
                    WriteSession.user_id == user_id,
                )
            ).scalar_one_or_none()
            if session is None:
                raise ValueError("Write session not found")

        day = self.db.execute(
            select(JournalDay).where(
                JournalDay.user_id == user_id,
                JournalDay.day_date == resolved,
            )
        ).scalar_one_or_none()
        active_entries: list[JournalEntry] = []
        if day is not None:
            active_entries = list(
                self.db.execute(
                    select(JournalEntry)
                    .where(
                        JournalEntry.day_id == day.id,
                        JournalEntry.superseded_by_entry_id.is_(None),
                    )
                    .order_by(JournalEntry.sequence_no.asc())
                ).scalars()
            )

        semantic_candidates = (
            self.semantic.search_same_day_candidates(
                day.id,
                sanitized_text,
                limit=self.config.decision.candidate_limit,
            )
            if day is not None
            else []
        )
        top_similarity = semantic_candidates[0].similarity if semantic_candidates else 0.0
        coordinator_result = self.coordinator.decide(
            CoordinatorContext(
                resolved_date=resolved,
                user_text=sanitized_text,
                candidate_entry_ids=[candidate.entry_id for candidate in semantic_candidates],
                top_similarity=top_similarity,
                existing_entries_count=len(active_entries),
            )
        )
        decision = coordinator_result.decision
        relation = semantic_relation(
            top_similarity,
            dedup_threshold=self.config.decision.dedup_similarity_threshold,
        )
        effective_action = decision.action
        decision_reason = decision.reason
        if relation == "same_event":
            effective_action = Action.noop if top_similarity >= 0.97 else Action.update
            decision_reason += " Semantična preverba: isti dogodek."
        elif relation == "potential_update" and decision.candidate_entry_ids:
            effective_action = Action.update
            decision_reason += " Semantična preverba: verjetna posodobitev istega dogodka."
        elif relation == "distinct" and decision.action in {Action.noop, Action.update}:
            effective_action = Action.append if active_entries else Action.create
            decision_reason += " Semantična preverba: ločen dogodek."

        existing_entries = [
            {
                "id": entry.id,
                "sequence_no": entry.sequence_no,
                "event_text_sl": entry.event_text_sl,
                "source_user_text": entry.source_user_text,
                "updated_from_entry_id": entry.updated_from_entry_id,
            }
            for entry in active_entries
        ]
        editor_result = self.editor.propose(
            EditorContext(
                action=effective_action,
                source_text=sanitized_text,
                instruction=sanitized_instruction,
                existing_entries=existing_entries,
                candidate_entry_ids=decision.candidate_entry_ids,
            )
        )
        proposed_entries = editor_result.entries

        current_day_text = render_day_text(resolved, [entry.event_text_sl for entry in active_entries])
        proposed_day_text = render_day_text(
            resolved, [str(entry["event_text_sl"]) for entry in proposed_entries]
        )
        diff_text = generate_unified_diff(
            current_day_text,
            proposed_day_text,
            file_label=f"day/{resolved.isoformat()}",
        )
        op = WriteOperation(
            session_id=session.id,
            action=OperationAction(effective_action.value),
            decision_json={
                **decision.model_dump(mode="json"),
                "effective_action": effective_action.value,
                "semantic_relation": relation,
                "reason": decision_reason,
            },
            proposed_entries_json=proposed_entries,
            diff_text=diff_text,
            status=OperationStatus.pending,
        )
        self.db.add(op)
        self.db.commit()
        self.db.refresh(op)
        self.db.refresh(session)
        return {
            "session_id": session.id,
            "operation_id": op.id,
            "resolved_date": decision.resolved_date.isoformat(),
            "action": effective_action.value,
            "reason": decision_reason,
            "candidate_entry_ids": decision.candidate_entry_ids,
            "semantic_relation": relation,
            "semantic_candidates": [
                {"entry_id": c.entry_id, "similarity": c.similarity, "event_text_sl": c.event_text_sl}
                for c in semantic_candidates
            ],
            "proposed_entries": proposed_entries,
            "diff_text": diff_text,
            "warnings": self.model_warnings + coordinator_result.warnings + editor_result.warnings,
        }

    def propose_day_edit(
        self,
        *,
        user_id: int,
        day_date: str,
        edited_content: str,
        session_id: int | None,
    ) -> dict[str, object]:
        target_day = date_cls.fromisoformat(day_date)
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")

        if session_id is None:
            session = WriteSession(user_id=user_id, day_date=target_day, status=SessionStatus.draft)
            self.db.add(session)
            self.db.flush()
        else:
            session = self.db.execute(
                select(WriteSession).where(
                    WriteSession.id == session_id,
                    WriteSession.user_id == user_id,
                )
            ).scalar_one_or_none()
            if session is None:
                raise ValueError("Write session not found")
            if session.day_date != target_day:
                raise ValueError("Write session day does not match selected day")

        day = self.db.execute(
            select(JournalDay).where(
                JournalDay.user_id == user_id,
                JournalDay.day_date == target_day,
            )
        ).scalar_one_or_none()
        active_entries: list[JournalEntry] = []
        if day is not None:
            active_entries = list(
                self.db.execute(
                    select(JournalEntry)
                    .where(
                        JournalEntry.day_id == day.id,
                        JournalEntry.superseded_by_entry_id.is_(None),
                    )
                    .order_by(JournalEntry.sequence_no.asc())
                ).scalars()
            )

        sanitized = sanitize_model_text(edited_content)
        proposed_events = parse_day_edit_text(sanitized)
        current_events = [entry.event_text_sl for entry in active_entries]

        if current_events == proposed_events:
            action = Action.noop
            reason = "Urejanje dneva ne uvaja sprememb."
        elif not current_events and proposed_events:
            action = Action.create
            reason = "Ustvarjen bo prvi vnos za izbran dan."
        else:
            action = Action.update
            reason = "Ročno urejanje bo posodobilo vse vnose izbranega dne."

        proposed_entries = [
            {
                "sequence_no": idx + 1,
                "event_text_sl": event,
                "source_user_text": event,
                "updated_from_entry_id": None,
            }
            for idx, event in enumerate(proposed_events)
        ]

        diff_text = generate_unified_diff(
            render_day_text(target_day, current_events),
            render_day_text(target_day, proposed_events),
            file_label=f"day/{target_day.isoformat()}",
        )
        op = WriteOperation(
            session_id=session.id,
            action=OperationAction(action.value),
            decision_json={
                "resolved_date": target_day.isoformat(),
                "action": action.value,
                "candidate_entry_ids": [],
                "reason": reason,
                "manual_edit": True,
                "replace_all": True,
            },
            proposed_entries_json=proposed_entries,
            diff_text=diff_text,
            status=OperationStatus.pending,
        )
        self.db.add(op)
        self.db.commit()
        self.db.refresh(op)
        self.db.refresh(session)
        return {
            "session_id": session.id,
            "operation_id": op.id,
            "resolved_date": target_day.isoformat(),
            "action": action.value,
            "reason": reason,
            "candidate_entry_ids": [],
            "semantic_relation": "manual_edit",
            "semantic_candidates": [],
            "proposed_entries": proposed_entries,
            "diff_text": diff_text,
            "warnings": [],
        }

    def confirm(self, *, user_id: int, session_id: int, idempotency_key: str) -> dict[str, object]:
        return self.write_tx.confirm(
            user_id=user_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )

    def cancel(self, *, user_id: int, session_id: int) -> dict[str, object]:
        session = self.db.execute(
            select(WriteSession).where(
                WriteSession.id == session_id,
                WriteSession.user_id == user_id,
            )
        ).scalar_one_or_none()
        if session is None:
            raise ValueError("Write session not found")
        session.status = SessionStatus.cancelled
        self.db.commit()
        return {"status": "cancelled", "session_id": session_id}
