from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from ai_daily_journal.config.loader import load_config, load_secrets
from ai_daily_journal.db.models import Base
from ai_daily_journal.paths import default_config_path, default_env_path

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_db_url() -> str:
    cfg_path = default_config_path()
    env_path = default_env_path()
    if cfg_path.exists() and env_path.exists():
        cfg = load_config(cfg_path)
        env = load_secrets(env_path)
        value = env.get(cfg.database.url_env)
        if value:
            return value
    fallback = os.getenv("AI_DAILY_JOURNAL_DB_URL")
    if fallback:
        return fallback
    raise RuntimeError("Database URL not configured. Set config.yaml/.env or AI_DAILY_JOURNAL_DB_URL.")


def run_migrations_offline() -> None:
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = get_db_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
