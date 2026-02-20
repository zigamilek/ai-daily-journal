# AI Daily Journal

AI-assisted daily journaling with a DB-first architecture and explicit proposal/diff confirmation workflow.

## Core Principles

- Canonical source of truth is PostgreSQL.
- Day content shown in UI is rendered directly from DB entries.
- Proposal is shown before write; DB write only happens after explicit confirm.
- Slovenian output is enforced for event text generation.
- Idempotency and operation audit records are built into write confirmations.

## Tech Stack

- Backend: Python, FastAPI, Typer CLI (`aijournal`)
- DB: PostgreSQL + `pgvector`
- ORM/migrations: SQLAlchemy + Alembic
- Frontend: React + Vite + TypeScript
- Runtime: systemd service (`ai-daily-journal.service`)

## Repository Layout

- `src/ai_daily_journal/` backend code
- `web/` frontend code
- `migrations/` Alembic migrations
- `deploy/systemd/ai-daily-journal.service` systemd unit
- `deploy/proxmox/ai-daily-journal-lxc.sh` Proxmox host installer
- `install/ai-daily-journal-install.sh` in-container installer

## Local Development

### 1) Backend setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.yaml.example config.yaml
cp .env.example .env
```

### 2) PostgreSQL bootstrap

Create DB and role (example):

```sql
CREATE ROLE ai_daily_journal LOGIN PASSWORD 'change_me';
CREATE DATABASE ai_daily_journal OWNER ai_daily_journal;
\c ai_daily_journal
CREATE EXTENSION IF NOT EXISTS vector;
```

Then update `.env`:

```bash
AI_DAILY_JOURNAL_DB_URL=postgresql+psycopg://ai_daily_journal:change_me@127.0.0.1:5432/ai_daily_journal
```

### 3) Run migrations

```bash
alembic upgrade head
```

### 4) Start backend

```bash
aijournal serve --config ./config.yaml
```

### 5) Start frontend

```bash
cd web
npm install
npm run dev
```

## Configuration Model

- `config.yaml` is the source of truth for app behavior.
- `.env` is for secrets only.
- Startup validation is strict (`pydantic`, extra keys forbidden).

Key sections:

- `server`
- `api_ui`
- `database`
- `models` (`coordinator`, `editor`, `embeddings`)
- `decision`
- `logging`
- `diagnostics`
- `runtime`

## CLI Usage

```bash
aijournal --version
aijournal onboarding
aijournal serve --config /path/to/config.yaml
aijournal service start
aijournal service stop
aijournal service restart
aijournal service status
aijournal update
aijournal paths
aijournal diagnostics
aijournal logs
aijournal logs --follow
aijournal logs --file
```

## API Health/Diagnostics

- `GET /healthz`
- `GET /readyz`
- `GET /diagnostics`

## Write Flow

1. User sends journal text.
2. Date is resolved from Slovenian phrase semantics.
3. Semantic candidates are fetched from same day via embeddings.
4. Coordinator returns strict JSON decision (`noop|append|update|create`).
5. Editor generates proposed Slovenian event text.
6. Unified diff is generated and returned.
7. On confirm, transaction applies operation + idempotency check.
8. Final day content is rendered from committed DB state.

## Automated Tests

Run:

```bash
pytest
```

Coverage includes:

- Date semantics
- Coordinator schema validation + retries
- Semantic dedup decisions
- Proposal/diff generation
- Confirm loop revisions
- Idempotency protection
- Day-content rendering consistency
- CLI behavior
- Migration metadata compatibility

## Proxmox One-Liner Install (Host)

Example (replace repo URL/branch as needed):

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/zigamilek/ai-daily-journal/master/deploy/proxmox/ai-daily-journal-lxc.sh)"
```

Or clone and run directly:

```bash
git clone https://github.com/zigamilek/ai-daily-journal.git
cd ai-daily-journal
bash deploy/proxmox/ai-daily-journal-lxc.sh
```

## Installer Notes

- Host script creates Debian 12 LXC and executes in-container install.
- In-container installer installs dependencies, PostgreSQL/pgvector, migrations, systemd service.
- Defaults are non-destructive for `config.yaml` and `.env`.
