from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ai-daily-journal"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    override = os.getenv("AI_DAILY_JOURNAL_CONFIG")
    if override:
        return Path(override).expanduser()
    return repo_root() / "config.yaml"


def default_env_path() -> Path:
    override = os.getenv("AI_DAILY_JOURNAL_ENV")
    if override:
        return Path(override).expanduser()
    return repo_root() / ".env"


def prompts_dir() -> Path:
    return repo_root() / "prompts"


def style_guide_path() -> Path:
    return prompts_dir() / "style-guide.md"


def logs_dir() -> Path:
    return repo_root() / "logs"


def logs_file() -> Path:
    return logs_dir() / "ai-daily-journal.log"


def projection_root() -> Path:
    return repo_root() / "projections"


def systemd_unit_path() -> Path:
    return Path("/etc/systemd/system/ai-daily-journal.service")
