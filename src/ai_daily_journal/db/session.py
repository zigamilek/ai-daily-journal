from __future__ import annotations

from pathlib import Path
from typing import Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_daily_journal.config import resolve_secret
from ai_daily_journal.config.schema import AppConfig

SessionFactory = Callable[[], Session]


def create_engine_from_config(config: AppConfig, env: dict[str, str]) -> Engine:
    url = resolve_secret(env, config.database.url_env)
    kwargs: dict[str, object] = {"echo": config.database.echo_sql, "future": True}
    if not url.startswith("sqlite"):
        kwargs["pool_size"] = config.database.pool_size
        kwargs["max_overflow"] = config.database.max_overflow
    return create_engine(url, **kwargs)


def build_session_factory(engine: Engine) -> SessionFactory:
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return maker


def get_session_factory_from_app(app) -> SessionFactory:  # noqa: ANN001
    existing = getattr(app.state, "session_factory", None)
    if existing is not None:
        return existing
    cfg = app.state.config
    if cfg is None:
        raise RuntimeError("Configuration not loaded")
    env_path = Path(app.state.repo_root) / ".env"
    from ai_daily_journal.config.loader import load_secrets

    env = load_secrets(env_path)
    engine = create_engine_from_config(cfg, env)
    factory = build_session_factory(engine)
    app.state.db_engine = engine
    app.state.session_factory = factory
    return factory
