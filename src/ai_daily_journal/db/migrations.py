from __future__ import annotations

from sqlalchemy import Engine, text


def current_migration_version(engine: Engine) -> str | None:
    with engine.connect() as conn:
        try:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        except Exception:  # noqa: BLE001
            return None
        if row is None:
            return None
        return str(row[0])


def migration_status(engine: Engine) -> dict[str, object]:
    version = current_migration_version(engine)
    return {"has_alembic_version": version is not None, "current_version": version}
