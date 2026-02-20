from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_daily_journal.db.session import get_session_factory_from_app
from ai_daily_journal.services.auth import AuthService
from ai_daily_journal.services.journal_read import JournalReadService
from ai_daily_journal.services.write_flow import JournalWriteService

router = APIRouter(prefix="/api/journal", tags=["journal"])


class ProposeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None
    instruction: str | None = None


class ConfirmRequest(BaseModel):
    session_id: int
    idempotency_key: str = Field(min_length=8, max_length=128)


class CancelRequest(BaseModel):
    session_id: int


class DayEditRequest(BaseModel):
    content: str = Field(min_length=0, max_length=12000)
    session_id: int | None = None


def _current_user_id(request: Request) -> int:
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
        return user.id


@router.get("/tree")
def tree(request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        return {"tree": JournalReadService(db).tree(user_id)}


@router.get("/days/{day_date}")
def day_file(day_date: str, request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        service = JournalReadService(db)
        content = service.render_day_content(user_id, day_date)
        if content is None:
            raise HTTPException(status_code=404, detail="Day not found")
        return {"day_date": day_date, "content": content}


@router.get("/latest")
def latest(request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        service = JournalReadService(db)
        latest_day = service.latest_day(user_id)
        if latest_day is None:
            return {"day_date": None, "content": ""}
        return {"day_date": latest_day.day_date.isoformat(), "content": service.render_day_content(user_id, latest_day.day_date.isoformat())}


@router.post("/propose")
def propose(payload: ProposeRequest, request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    cfg = request.app.state.config
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        service = JournalWriteService(db, cfg)
        try:
            return service.propose(
                user_id=user_id,
                source_text=payload.text,
                session_id=payload.session_id,
                instruction=payload.instruction,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/days/{day_date}/edit-propose")
def propose_day_edit(day_date: str, payload: DayEditRequest, request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    cfg = request.app.state.config
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        service = JournalWriteService(db, cfg)
        try:
            return service.propose_day_edit(
                user_id=user_id,
                day_date=day_date,
                edited_content=payload.content,
                session_id=payload.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/confirm")
def confirm(payload: ConfirmRequest, request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    cfg = request.app.state.config
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        service = JournalWriteService(db, cfg)
        try:
            return service.confirm(
                user_id=user_id,
                session_id=payload.session_id,
                idempotency_key=payload.idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cancel")
def cancel(payload: CancelRequest, request: Request) -> dict[str, object]:
    user_id = _current_user_id(request)
    cfg = request.app.state.config
    session_factory = get_session_factory_from_app(request.app)
    with session_factory() as db:
        service = JournalWriteService(db, cfg)
        try:
            return service.cancel(user_id=user_id, session_id=payload.session_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc
