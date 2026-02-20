from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from ai_daily_journal.db.session import get_session_factory_from_app
from ai_daily_journal.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    timezone: str = "Europe/Ljubljana"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(payload: RegisterRequest, request: Request) -> dict[str, object]:
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        user = AuthService(db).register_user(payload.email, payload.password, payload.timezone)
        return {"id": user.id, "email": user.email}


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    cfg = request.app.state.config
    if cfg is None:
        raise HTTPException(status_code=500, detail="Config missing")

    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        auth = AuthService(db)
        token = auth.authenticate(payload.email, payload.password)
        if token is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        response.set_cookie(
            cfg.api_ui.session_cookie_name,
            token,
            httponly=True,
            max_age=cfg.api_ui.session_ttl_seconds,
            samesite="lax",
        )
        return {"status": "ok"}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    cfg = request.app.state.config
    cookie_name = cfg.api_ui.session_cookie_name if cfg else "aijournal_session"
    response.delete_cookie(cookie_name)
    return {"status": "ok"}


@router.get("/me")
def me(request: Request) -> dict[str, object]:
    cfg = request.app.state.config
    if cfg is None:
        raise HTTPException(status_code=500, detail="Config missing")
    token = request.cookies.get(cfg.api_ui.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        user = AuthService(db).user_from_session_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid session")
        return {"id": user.id, "email": user.email, "timezone": user.timezone}
