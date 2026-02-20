from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily_journal.db.models import JournalEntry, SemanticDocument


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0 or norm_r == 0:
        return 0.0
    return dot / (norm_l * norm_r)


def deterministic_embedding(text: str, dimensions: int) -> list[float]:
    base = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    idx = 0
    while len(out) < dimensions:
        byte = base[idx % len(base)]
        out.append((byte / 255.0) * 2.0 - 1.0)
        idx += 1
    return out


Embedder = Callable[[str], list[float]]


@dataclass(slots=True)
class SemanticCandidate:
    entry_id: int
    similarity: float
    event_text_sl: str


class SemanticSearchService:
    def __init__(
        self,
        db: Session,
        *,
        embeddings_model_name: str,
        dimensions: int = 1536,
        embedder: Embedder | None = None,
    ) -> None:
        self.db = db
        self.embeddings_model_name = embeddings_model_name
        self.dimensions = dimensions
        self.embedder = embedder or (lambda text: deterministic_embedding(text, dimensions))

    def embed(self, text: str) -> list[float]:
        vector = self.embedder(text)
        if len(vector) != self.dimensions:
            raise ValueError("Embedding dimensions mismatch")
        return vector

    def upsert_entry_embedding(self, entry_id: int, event_text_sl: str) -> None:
        vector = self.embed(event_text_sl)
        existing = self.db.execute(
            select(SemanticDocument).where(SemanticDocument.entry_id == entry_id)
        ).scalar_one_or_none()
        if existing is None:
            self.db.add(
                SemanticDocument(
                    entry_id=entry_id,
                    embedding=vector,
                    model_name=self.embeddings_model_name,
                )
            )
        else:
            existing.embedding = vector
            existing.model_name = self.embeddings_model_name

    def search_same_day_candidates(
        self,
        day_id: int,
        source_text: str,
        *,
        limit: int,
    ) -> list[SemanticCandidate]:
        source_vector = self.embed(source_text)
        rows = self.db.execute(
            select(SemanticDocument, JournalEntry)
            .join(JournalEntry, JournalEntry.id == SemanticDocument.entry_id)
            .where(
                JournalEntry.day_id == day_id,
                JournalEntry.superseded_by_entry_id.is_(None),
            )
        ).all()
        scored = [
            SemanticCandidate(
                entry_id=entry.id,
                similarity=cosine_similarity(source_vector, list(document.embedding)),
                event_text_sl=entry.event_text_sl,
            )
            for document, entry in rows
        ]
        scored.sort(key=lambda item: item.similarity, reverse=True)
        return scored[:limit]


def semantic_relation(similarity: float, *, dedup_threshold: float) -> str:
    if similarity >= max(dedup_threshold, 0.97):
        return "same_event"
    if similarity >= dedup_threshold:
        return "potential_update"
    return "distinct"
