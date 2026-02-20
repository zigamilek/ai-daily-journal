from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class EmbeddingType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):  # noqa: ANN001
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return value
        return [float(v) for v in value]

    def process_result_value(self, value, dialect):  # noqa: ANN001
        if value is None:
            return value
        return [float(v) for v in value]


class SessionStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"
    cancelled = "cancelled"


class OperationStatus(str, Enum):
    pending = "pending"
    applied = "applied"
    failed = "failed"
    cancelled = "cancelled"


class OperationAction(str, Enum):
    noop = "noop"
    append = "append"
    update = "update"
    create = "create"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Ljubljana", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship("User")


class JournalDay(Base):
    __tablename__ = "ai_daily_journal_days"
    __table_args__ = (UniqueConstraint("user_id", "day_date", name="uq_day_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    entries: Mapped[list["JournalEntry"]] = relationship(
        "JournalEntry", back_populates="day", cascade="all, delete-orphan"
    )


class JournalEntry(Base):
    __tablename__ = "ai_daily_journal_entries"
    __table_args__ = (UniqueConstraint("day_id", "sequence_no", name="uq_entry_day_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_id: Mapped[int] = mapped_column(
        ForeignKey("ai_daily_journal_days.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    event_text_sl: Mapped[str] = mapped_column(Text, nullable=False)
    source_user_text: Mapped[str] = mapped_column(Text, nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    superseded_by_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_daily_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    updated_from_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_daily_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    day: Mapped[JournalDay] = relationship("JournalDay", back_populates="entries")


class SemanticDocument(Base):
    __tablename__ = "semantic_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("ai_daily_journal_entries.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    embedding: Mapped[list[float]] = mapped_column(EmbeddingType(1536), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class WriteSession(Base):
    __tablename__ = "write_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status"), default=SessionStatus.draft, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class WriteOperation(Base):
    __tablename__ = "write_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("write_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[OperationAction] = mapped_column(
        SAEnum(OperationAction, name="operation_action"), nullable=False
    )
    decision_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_entries_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    diff_text: Mapped[str] = mapped_column(Text, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[OperationStatus] = mapped_column(
        SAEnum(OperationStatus, name="operation_status"),
        default=OperationStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("key", "user_id", name="uq_idempotency_key_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    operation_id: Mapped[int | None] = mapped_column(
        ForeignKey("write_operations.id", ondelete="SET NULL"), nullable=True
    )


class SchemaVersion(Base):
    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
