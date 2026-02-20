from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_daily_journal.api.routes.auth import router as auth_router
from ai_daily_journal.api.routes.journal import router as journal_router
from ai_daily_journal.api.routes.system import router as system_router
from ai_daily_journal.config import load_config
from ai_daily_journal.paths import default_config_path


def create_app() -> FastAPI:
    config_path = default_config_path()
    app = FastAPI(title="AI Daily Journal", version="0.1.0")
    if config_path.exists():
        cfg = load_config(config_path)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.api_ui.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.state.config = cfg
    else:
        app.state.config = None

    app.state.repo_root = str(Path(__file__).resolve().parents[3])
    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(journal_router)
    return app
