"""init ai daily journal core

Revision ID: 20260220_000001
Revises:
Create Date: 2026-02-20 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "20260220_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    session_status = sa.Enum("draft", "confirmed", "cancelled", name="session_status")
    operation_action = sa.Enum("noop", "append", "update", "create", name="operation_action")
    operation_status = sa.Enum("pending", "applied", "failed", "cancelled", name="operation_status")
    session_status.create(op.get_bind(), checkfirst=True)
    operation_action.create(op.get_bind(), checkfirst=True)
    operation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("token", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ai_daily_journal_days",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "day_date", name="uq_day_user_date"),
    )
    op.create_index("ix_day_user_id", "ai_daily_journal_days", ["user_id"], unique=False)
    op.create_index("ix_day_day_date", "ai_daily_journal_days", ["day_date"], unique=False)

    op.create_table(
        "ai_daily_journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "day_id",
            sa.Integer(),
            sa.ForeignKey("ai_daily_journal_days.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_text_sl", sa.Text(), nullable=False),
        sa.Column("source_user_text", sa.Text(), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "superseded_by_entry_id",
            sa.Integer(),
            sa.ForeignKey("ai_daily_journal_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_from_entry_id",
            sa.Integer(),
            sa.ForeignKey("ai_daily_journal_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("day_id", "sequence_no", name="uq_entry_day_sequence"),
    )
    op.create_index("ix_entry_day_id", "ai_daily_journal_entries", ["day_id"], unique=False)
    op.create_index("ix_entry_hash", "ai_daily_journal_entries", ["event_hash"], unique=False)

    op.create_table(
        "semantic_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "entry_id",
            sa.Integer(),
            sa.ForeignKey("ai_daily_journal_entries.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_semantic_documents_embedding "
        "ON semantic_documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "write_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_date", sa.Date(), nullable=False),
        sa.Column("status", session_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_write_sessions_user_id", "write_sessions", ["user_id"], unique=False)
    op.create_index("ix_write_sessions_day_date", "write_sessions", ["day_date"], unique=False)

    op.create_table(
        "write_operations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("write_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", operation_action, nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("proposed_entries_json", sa.JSON(), nullable=False),
        sa.Column("diff_text", sa.Text(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", operation_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_write_operations_session_id", "write_operations", ["session_id"], unique=False)

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "operation_id",
            sa.Integer(),
            sa.ForeignKey("write_operations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("key", "user_id", name="uq_idempotency_key_user"),
    )
    op.create_index("ix_idempotency_user_id", "idempotency_keys", ["user_id"], unique=False)

    op.create_table(
        "schema_version",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(length=64), nullable=False, unique=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        "INSERT INTO schema_version (version, applied_at) "
        f"VALUES ('{revision}', NOW())"
    )


def downgrade() -> None:
    op.drop_table("schema_version")
    op.drop_index("ix_idempotency_user_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_write_operations_session_id", table_name="write_operations")
    op.drop_table("write_operations")
    op.drop_index("ix_write_sessions_day_date", table_name="write_sessions")
    op.drop_index("ix_write_sessions_user_id", table_name="write_sessions")
    op.drop_table("write_sessions")
    op.execute("DROP INDEX IF EXISTS ix_semantic_documents_embedding")
    op.drop_table("semantic_documents")
    op.drop_index("ix_entry_hash", table_name="ai_daily_journal_entries")
    op.drop_index("ix_entry_day_id", table_name="ai_daily_journal_entries")
    op.drop_table("ai_daily_journal_entries")
    op.drop_index("ix_day_day_date", table_name="ai_daily_journal_days")
    op.drop_index("ix_day_user_id", table_name="ai_daily_journal_days")
    op.drop_table("ai_daily_journal_days")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS operation_status")
    op.execute("DROP TYPE IF EXISTS operation_action")
    op.execute("DROP TYPE IF EXISTS session_status")
