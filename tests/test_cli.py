from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from typer.testing import CliRunner

from ai_daily_journal import __version__
from ai_daily_journal.cli.main import app
import ai_daily_journal.cli.main as cli_main
from tests.helpers import make_config


runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_service_status_reports_service_and_health(monkeypatch) -> None:
    def fake_run(_cmd, check=True):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="active\n", stderr="")

    class FakeResponse:
        status_code = 200

    monkeypatch.setattr(cli_main, "_run", fake_run)
    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: FakeResponse())
    result = runner.invoke(app, ["service", "status"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["service_state"] == "active"
    assert payload["healthz_ok"] is True


def test_diagnostics_command_with_sqlite(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    db_path = tmp_path / "diag.db"
    cfg = make_config()
    cfg.logging.log_dir = str((tmp_path / "logs").resolve())
    config_path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")), encoding="utf-8")
    env_path.write_text(f"AI_DAILY_JOURNAL_DB_URL=sqlite+pysqlite:///{db_path}\n", encoding="utf-8")
    monkeypatch.setenv("AI_DAILY_JOURNAL_CONFIG", str(config_path))
    monkeypatch.setenv("AI_DAILY_JOURNAL_ENV", str(env_path))

    result = runner.invoke(app, ["diagnostics"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["version"] == __version__
    assert payload["config_path"] == str(config_path.resolve())
    assert payload["db_ready"] is True
