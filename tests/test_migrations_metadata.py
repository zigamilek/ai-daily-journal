from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from ai_daily_journal.db.migrations import current_migration_version, migration_status


def test_migration_status_without_alembic_table(tmp_path: Path) -> None:
    db_path = tmp_path / "migrate.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    try:
        assert current_migration_version(engine) is None
        status = migration_status(engine)
        assert status["has_alembic_version"] is False
    finally:
        engine.dispose()


def test_initial_migration_contains_required_tables() -> None:
    migration = Path("migrations/versions/20260220_000001_init_ai_daily_journal_core.py")
    text = migration.read_text(encoding="utf-8")
    for table_name in [
        "ai_daily_journal_days",
        "ai_daily_journal_entries",
        "semantic_documents",
        "write_sessions",
        "write_operations",
        "idempotency_keys",
        "schema_version",
    ]:
        assert table_name in text


def test_initial_migration_uses_non_duplicating_enum_strategy() -> None:
    migration = Path("migrations/versions/20260220_000001_init_ai_daily_journal_core.py")
    text = migration.read_text(encoding="utf-8")
    assert "postgresql.ENUM(" in text
    assert "create_type=False" in text
