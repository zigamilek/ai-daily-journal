from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_daily_journal.db.models import Base, User
from tests.helpers import make_config


@pytest.fixture()
def test_config(tmp_path: Path):
    config = make_config()
    config.ai_daily_journal_projection.root_path = str((tmp_path / "projections").resolve())
    config.logging.log_dir = str((tmp_path / "logs").resolve())
    return config


@pytest.fixture()
def db_session(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def test_user(db_session: Session):
    user = User(
        email="user@example.com",
        password_hash="hash",
        timezone="Europe/Ljubljana",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
