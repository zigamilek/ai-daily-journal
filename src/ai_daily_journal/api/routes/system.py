from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ai_daily_journal import __version__
from ai_daily_journal.config import load_secrets
from ai_daily_journal.db.migrations import current_migration_version
from ai_daily_journal.db.session import create_engine_from_config
from ai_daily_journal.paths import default_env_path

router = APIRouter(tags=["system"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    cfg = request.app.state.config
    if cfg is None:
        return JSONResponse({"status": "not_ready", "reason": "config_missing"}, status_code=503)
    try:
        env = load_secrets(default_env_path())
        engine = create_engine_from_config(cfg, env)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return JSONResponse({"status": "ready", "db": "ok"}, status_code=200)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "not_ready", "reason": str(exc)}, status_code=503)


@router.get("/diagnostics")
def diagnostics(request: Request) -> dict[str, object]:
    cfg = request.app.state.config
    payload: dict[str, object] = {
        "version": __version__,
        "utc_now": datetime.now(timezone.utc).isoformat(),
        "config_loaded": cfg is not None,
    }
    if cfg is None:
        return payload

    env = load_secrets(default_env_path())
    try:
        engine = create_engine_from_config(cfg, env)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        payload["db_ready"] = True
        payload["migration_version"] = current_migration_version(engine)
    except Exception as exc:  # noqa: BLE001
        payload["db_ready"] = False
        payload["db_error"] = str(exc)
    payload["models"] = {
        "coordinator": cfg.models.coordinator.model_name,
        "editor": cfg.models.editor.model_name,
        "embeddings": cfg.models.embeddings.model_name,
    }
    return payload
