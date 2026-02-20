from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from ai_daily_journal.config.schema import LoggingConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(cfg: LoggingConfig) -> Path:
    log_dir = Path(cfg.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / cfg.log_file_name

    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))
    root.handlers.clear()

    handler = RotatingFileHandler(
        log_file,
        maxBytes=cfg.max_bytes,
        backupCount=cfg.backup_count,
        encoding="utf-8",
    )
    if cfg.format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.addHandler(handler)
    return log_file
