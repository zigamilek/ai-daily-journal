from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

import typer
import uvicorn

from ai_daily_journal import __version__
from ai_daily_journal.api.app import create_app
from ai_daily_journal.config import ConfigError, load_config, load_secrets
from ai_daily_journal.db.migrations import current_migration_version, migration_status
from ai_daily_journal.db.session import create_engine_from_config
from ai_daily_journal.logging_setup import configure_logging
from ai_daily_journal.paths import (
    default_config_path,
    default_env_path,
    logs_dir,
    logs_file,
    projection_root,
    prompts_dir,
    repo_root,
    style_guide_path,
    systemd_unit_path,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)
service_app = typer.Typer(no_args_is_help=True)
app.add_typer(service_app, name="service")


def _print_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _ensure_choice(
    prompt: str, *, default: Literal["keep", "overwrite", "cancel"] = "keep"
) -> Literal["keep", "overwrite", "cancel"]:
    raw = typer.prompt(
        f"{prompt} [keep/overwrite/cancel]",
        default=default,
        show_default=True,
    )
    choice = raw.strip().lower()
    if choice not in {"keep", "overwrite", "cancel"}:
        raise typer.BadParameter("Choice must be keep, overwrite, or cancel.")
    return choice  # type: ignore[return-value]


def _write_if_allowed(path: Path, content: str) -> None:
    if path.exists():
        action = _ensure_choice(f"{path} already exists.")
        if action == "cancel":
            raise typer.Abort()
        if action == "keep":
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True, capture_output=True)


@app.callback(invoke_without_command=True)
def _root(
    version: bool = typer.Option(False, "--version", help="Print version and exit.")
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)


@app.command("onboarding")
def onboarding() -> None:
    """Interactive setup wizard."""
    cfg_path = default_config_path()
    env_path = default_env_path()
    style_path = style_guide_path()

    host = typer.prompt("Server host", default="0.0.0.0")
    port = typer.prompt("Server port", default="8080")
    timezone = typer.prompt("Default timezone", default="Europe/Ljubljana")
    projection_dir = typer.prompt("Projection root path", default="./projections")
    coordinator_model = typer.prompt("Coordinator model", default="gpt-4.1-mini")
    editor_model = typer.prompt("Editor model", default="gpt-4.1")
    embeddings_model = typer.prompt("Embeddings model", default="text-embedding-3-small")

    config_text = f"""server:
  host: "{host}"
  port: {int(port)}
  public_base_url: "http://127.0.0.1:{int(port)}"
api_ui:
  cors_origins: ["http://127.0.0.1:5173"]
  session_cookie_name: "aijournal_session"
  session_ttl_seconds: 86400
database:
  url_env: "AI_DAILY_JOURNAL_DB_URL"
  pool_size: 10
  max_overflow: 20
  echo_sql: false
ai_daily_journal_projection:
  root_path: "{projection_dir}"
  atomic_write_mode: true
models:
  provider: "openai_compatible"
  coordinator:
    model_name: "{coordinator_model}"
    temperature: 0.0
    max_retries: 2
    base_url: "https://api.openai.com/v1"
    api_key_env: "AI_DAILY_JOURNAL_COORDINATOR_API_KEY"
  editor:
    model_name: "{editor_model}"
    temperature: 0.0
    max_retries: 2
    base_url: "https://api.openai.com/v1"
    api_key_env: "AI_DAILY_JOURNAL_EDITOR_API_KEY"
  embeddings:
    enabled: true
    model_name: "{embeddings_model}"
    dimensions: 1536
    base_url: "https://api.openai.com/v1"
    api_key_env: "AI_DAILY_JOURNAL_EMBEDDINGS_API_KEY"
decision:
  dedup_similarity_threshold: 0.88
  candidate_limit: 10
logging:
  level: "INFO"
  format: "json"
  log_dir: "./logs"
  log_file_name: "ai-daily-journal.log"
  max_bytes: 5242880
  backup_count: 5
diagnostics:
  health_timeout_seconds: 2
  readiness_timeout_seconds: 5
runtime:
  timezone: "{timezone}"
"""

    env_text = """AI_DAILY_JOURNAL_DB_URL=postgresql+psycopg://ai_daily_journal:change_me@127.0.0.1:5432/ai_daily_journal
AI_DAILY_JOURNAL_COORDINATOR_API_KEY=
AI_DAILY_JOURNAL_EDITOR_API_KEY=
AI_DAILY_JOURNAL_EMBEDDINGS_API_KEY=
AI_DAILY_JOURNAL_SESSION_SECRET=change_me
"""
    style_text = """# AI Daily Journal - Slovene Style Guide

- Piši v naravni, jedrnati slovenščini.
- Ohrani dejstva in časovni kontekst.
- Ne dodajaj izmišljenih podrobnosti.
- Ob posodobitvah ohrani ton in namen uporabnika.
"""

    _write_if_allowed(cfg_path, config_text)
    _write_if_allowed(env_path, env_text)
    _write_if_allowed(style_path, style_text)

    try:
        _ = load_config(cfg_path)
    except ConfigError as exc:
        raise typer.Exit(code=2) from typer.BadParameter(str(exc))
    typer.echo(f"Onboarding complete. Config validated at {cfg_path}")


@app.command("serve")
def serve(
    config: Path = typer.Option(..., "--config", exists=True, readable=True, dir_okay=False)
) -> None:
    """Start web server."""
    cfg = load_config(config)
    configure_logging(cfg.logging)
    uvicorn.run(
        "ai_daily_journal.api.app:create_app",
        host=cfg.server.host,
        port=cfg.server.port,
        factory=True,
    )


@service_app.command("start")
def service_start() -> None:
    _run(["systemctl", "start", "ai-daily-journal.service"])
    typer.echo("ai-daily-journal.service started")


@service_app.command("stop")
def service_stop() -> None:
    _run(["systemctl", "stop", "ai-daily-journal.service"])
    typer.echo("ai-daily-journal.service stopped")


@service_app.command("restart")
def service_restart() -> None:
    _run(["systemctl", "restart", "ai-daily-journal.service"])
    typer.echo("ai-daily-journal.service restarted")


@service_app.command("status")
def service_status() -> None:
    proc = _run(["systemctl", "is-active", "ai-daily-journal.service"], check=False)
    service_state = proc.stdout.strip() or "unknown"
    health_url = "http://127.0.0.1:8080/healthz"
    health_ok = False
    try:
        import httpx

        response = httpx.get(health_url, timeout=2.0)
        health_ok = response.status_code == 200
    except Exception:
        health_ok = False
    _print_json({"service_state": service_state, "healthz_ok": health_ok, "healthz_url": health_url})


@app.command("update")
def update() -> None:
    """Safe in-place service update."""
    venv_pip = repo_root() / ".venv" / "bin" / "pip"
    pip_cmd = [str(venv_pip)] if venv_pip.exists() else [sys.executable, "-m", "pip"]
    env = os.environ.copy()
    env.setdefault("AI_DAILY_JOURNAL_CONFIG", str(default_config_path().resolve()))
    env.setdefault("AI_DAILY_JOURNAL_ENV", str(default_env_path().resolve()))

    commands = [
        ["systemctl", "stop", "ai-daily-journal.service"],
        ["git", "pull", "--ff-only"],
        [*pip_cmd, "install", "-e", ".[dev]"],
        ["alembic", "upgrade", "head"],
        ["systemctl", "start", "ai-daily-journal.service"],
    ]
    for cmd in commands:
        proc = subprocess.run(cmd, check=False, text=True, capture_output=True, env=env)
        if proc.returncode != 0:
            typer.echo(f"Update failed at command: {' '.join(cmd)}", err=True)
            typer.echo(proc.stdout, err=True)
            typer.echo(proc.stderr, err=True)
            status = _run(["systemctl", "status", "ai-daily-journal.service", "--no-pager"], check=False)
            typer.echo(status.stdout, err=True)
            typer.echo(status.stderr, err=True)
            raise typer.Exit(code=proc.returncode)

    # health check retry
    import time

    import httpx

    health_url = "http://127.0.0.1:8080/healthz"
    for _ in range(5):
        try:
            if httpx.get(health_url, timeout=2.0).status_code == 200:
                typer.echo("Update complete and health check passed.")
                return
        except Exception:
            pass
        time.sleep(2)
    status = _run(["systemctl", "status", "ai-daily-journal.service", "--no-pager"], check=False)
    typer.echo(status.stdout, err=True)
    raise typer.Exit(code=3)


@app.command("paths")
def paths() -> None:
    cfg = load_config(default_config_path()) if default_config_path().exists() else None
    projection = (
        Path(cfg.ai_daily_journal_projection.root_path).resolve() if cfg else projection_root().resolve()
    )
    _print_json(
        {
            "config_yaml": str(default_config_path().resolve()),
            "env_file": str(default_env_path().resolve()),
            "prompts_dir": str(prompts_dir().resolve()),
            "style_guide_file": str(style_guide_path().resolve()),
            "markdown_projection_root": str(projection),
            "logs_dir": str(logs_dir().resolve()),
            "logs_file": str(logs_file().resolve()),
            "install_repo_path": str(repo_root().resolve()),
            "systemd_unit_path": str(systemd_unit_path()),
        }
    )


@app.command("diagnostics")
def diagnostics() -> None:
    cfg_path = default_config_path()
    env_path = default_env_path()
    payload: dict[str, object] = {"version": __version__, "config_path": str(cfg_path.resolve())}
    try:
        cfg = load_config(cfg_path)
        env = load_secrets(env_path)
        engine = create_engine_from_config(cfg, env)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        payload["db_ready"] = True
        payload["migration_version"] = current_migration_version(engine)
        payload["model_config"] = {
            "coordinator": cfg.models.coordinator.model_name,
            "editor": cfg.models.editor.model_name,
            "embeddings": cfg.models.embeddings.model_name,
        }
        payload["projection_writable"] = os.access(
            Path(cfg.ai_daily_journal_projection.root_path).resolve(), os.W_OK
        ) or not Path(cfg.ai_daily_journal_projection.root_path).exists()
        payload["service_urls"] = {
            "healthz": f"{cfg.server.public_base_url}/healthz",
            "readyz": f"{cfg.server.public_base_url}/readyz",
            "diagnostics": f"{cfg.server.public_base_url}/diagnostics",
        }
        payload["migration_status"] = migration_status(engine)
    except Exception as exc:  # noqa: BLE001
        payload["db_ready"] = False
        payload["error"] = str(exc)
    _print_json(payload)


@app.command("logs")
def logs(
    follow: bool = typer.Option(False, "--follow"),
    file: bool = typer.Option(False, "--file"),
) -> None:
    if file:
        path = logs_file().resolve()
        if not path.exists():
            raise typer.BadParameter(f"Log file not found: {path}")
        cmd = ["tail", "-n", "200", str(path)]
        if follow:
            cmd.insert(1, "-f")
        subprocess.run(cmd, check=False)
        return

    cmd = ["journalctl", "-u", "ai-daily-journal.service", "-n", "200", "--no-pager"]
    if follow:
        cmd.append("-f")
    subprocess.run(cmd, check=False)
