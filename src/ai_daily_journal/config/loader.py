from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import ValidationError

from ai_daily_journal.config.schema import AppConfig


class ConfigError(RuntimeError):
    pass


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping/object")
    return data


def load_config(config_path: Path) -> AppConfig:
    try:
        return AppConfig.model_validate(read_yaml(config_path))
    except ValidationError as exc:
        raise ConfigError(f"Invalid config: {exc}") from exc


def load_secrets(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    return {k: v for k, v in dotenv_values(env_path).items() if v is not None}


def resolve_secret(env: dict[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        raise ConfigError(f"Missing secret env var: {name}")
    return value
