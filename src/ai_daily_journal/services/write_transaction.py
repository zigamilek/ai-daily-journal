from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily_journal.db.models import (
    IdempotencyKey,
    JournalDay,
    JournalEntry,
    OperationStatus,
    SessionStatus,
    WriteOperation,
    WriteSession,
)
from ai_daily_journal.services.day_content import render_day_text
from ai_daily_journal.services.semantic_search import SemanticSearchService


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class WriteTransactionService:
    def __init__(
        self,
        db: Session,
        *,
        embeddings_model_name: str,
        embeddings_dimensions: int,
    ) -> None:
        self.db = db
        self.semantic = SemanticSearchService(
            db,
            embeddings_model_name=embeddings_model_name,
            dimensions=embeddings_dimensions,
        )

    def confirm(
        self,
        *,
        user_id: int,
        session_id: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        session = self.db.execute(
            select(WriteSession).where(
                WriteSession.id == session_id,
                WriteSession.user_id == user_id,
            )
        ).scalar_one_or_none()
        if session is None:
            raise ValueError("Write session not found")
        operation = self.db.execute(
            select(WriteOperation)
            .where(WriteOperation.session_id == session.id)
            .order_by(WriteOperation.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if operation is None:
            raise ValueError("No pending operation to confirm")

        request_hash = _hash_text(f"{session_id}:{operation.id}:{operation.diff_text}")
        existing_key = self.db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.user_id == user_id,
            )
        ).scalar_one_or_none()
        if existing_key is not None:
            if existing_key.request_hash != request_hash:
                raise ValueError("Idempotency key reused with different request payload")
            existing_key.last_seen_at = datetime.now(timezone.utc)
            self.db.commit()
            day = self.db.execute(
                select(JournalDay).where(
                    JournalDay.user_id == user_id,
                    JournalDay.day_date == session.day_date,
                )
            ).scalar_one_or_none()
            final_content = ""
            if day is not None:
                final_active = list(
                    self.db.execute(
                        select(JournalEntry)
                        .where(
                            JournalEntry.day_id == day.id,
                            JournalEntry.superseded_by_entry_id.is_(None),
                        )
                        .order_by(JournalEntry.sequence_no.asc())
                    ).scalars()
                )
                final_content = render_day_text(
                    day.day_date, [entry.event_text_sl for entry in final_active]
                )
            return {
                "status": "ok",
                "idempotent_replay": True,
                "operation_id": existing_key.operation_id,
                "day_date": session.day_date.isoformat(),
                "final_content": final_content,
            }

        day = self.db.execute(
            select(JournalDay).where(
                JournalDay.user_id == user_id,
                JournalDay.day_date == session.day_date,
            )
        ).scalar_one_or_none()
        if day is None:
            day = JournalDay(user_id=user_id, day_date=session.day_date, timezone="Europe/Ljubljana")
            self.db.add(day)
            self.db.flush()

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
        replace_all = bool(operation.decision_json.get("replace_all", False))
        if replace_all:
            for active in active_entries:
                self.db.delete(active)
            self.db.flush()
            active_by_sequence: dict[int, JournalEntry] = {}
        else:
            active_by_sequence = {entry.sequence_no: entry for entry in active_entries}

        proposed_entries = operation.proposed_entries_json
        for proposed in proposed_entries:
            seq = int(proposed["sequence_no"])
            text = str(proposed["event_text_sl"]).strip()
            source = str(proposed.get("source_user_text", ""))
            existing = active_by_sequence.get(seq)
            if existing is None:
                new_entry = JournalEntry(
                    day_id=day.id,
                    sequence_no=seq,
                    event_text_sl=text,
                    source_user_text=source,
                    event_hash=_hash_text(text),
                )
                self.db.add(new_entry)
                self.db.flush()
                self.semantic.upsert_entry_embedding(new_entry.id, text)
                continue
            if existing.event_text_sl != text:
                replacement = JournalEntry(
                    day_id=day.id,
                    sequence_no=seq,
                    event_text_sl=text,
                    source_user_text=source,
                    event_hash=_hash_text(text),
                    updated_from_entry_id=existing.id,
                )
                self.db.add(replacement)
                self.db.flush()
                existing.superseded_by_entry_id = replacement.id
                self.semantic.upsert_entry_embedding(replacement.id, text)

        operation.status = OperationStatus.applied
        operation.applied_at = datetime.now(timezone.utc)
        session.status = SessionStatus.confirmed
        self.db.add(
            IdempotencyKey(
                key=idempotency_key,
                user_id=user_id,
                request_hash=request_hash,
                operation_id=operation.id,
            )
        )
        self.db.commit()

        final_active = list(
            self.db.execute(
                select(JournalEntry)
                .where(
                    JournalEntry.day_id == day.id,
                    JournalEntry.superseded_by_entry_id.is_(None),
                )
                .order_by(JournalEntry.sequence_no.asc())
            ).scalars()
        )
        final_content = render_day_text(day.day_date, [entry.event_text_sl for entry in final_active])
        return {
            "status": "ok",
            "idempotent_replay": False,
            "operation_id": operation.id,
            "day_date": day.day_date.isoformat(),
            "final_content": final_content,
        }
