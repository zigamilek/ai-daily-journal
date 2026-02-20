from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily_journal.db.models import User, UserSession


class AuthService:
    def __init__(self, db: Session, session_ttl_seconds: int = 86_400) -> None:
        self.db = db
        self.session_ttl_seconds = session_ttl_seconds
        self._hasher = PasswordHasher()

    def register_user(self, email: str, password: str, timezone_name: str) -> User:
        existing = self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing is not None:
            raise ValueError("Email already registered")
        user = User(
            email=email,
            password_hash=self._hasher.hash(password),
            timezone=timezone_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> str | None:
        user = self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            return None
        try:
            self._hasher.verify(user.password_hash, password)
        except VerifyMismatchError:
            return None
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(seconds=self.session_ttl_seconds)
        self.db.add(UserSession(token=token, user_id=user.id, expires_at=expires))
        self.db.commit()
        return token

    def user_from_session_token(self, token: str) -> User | None:
        session = self.db.execute(select(UserSession).where(UserSession.token == token)).scalar_one_or_none()
        if session is None:
            return None
        if session.expires_at < datetime.now(timezone.utc):
            self.db.delete(session)
            self.db.commit()
            return None
        return self.db.get(User, session.user_id)
