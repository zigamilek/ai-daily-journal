#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="ai-daily-journal"
APP_USER="ai-daily-journal"
APP_GROUP="ai-daily-journal"
INSTALL_DIR="/opt/ai-daily-journal"
CONFIG_DIR="/etc/ai-daily-journal"
LOG_DIR="/var/log/ai-daily-journal"
DATA_DIR="/var/lib/ai-daily-journal"
VENV_DIR="${INSTALL_DIR}/.venv"
SYSTEMD_UNIT_DEST="/etc/systemd/system/ai-daily-journal.service"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
ENV_FILE="${CONFIG_DIR}/.env"

DB_NAME="${AI_DAILY_JOURNAL_DB_NAME:-ai_daily_journal}"
DB_USER="${AI_DAILY_JOURNAL_DB_USER:-ai_daily_journal}"
DB_PASSWORD="${AI_DAILY_JOURNAL_DB_PASSWORD:-}"
APP_REPO_URL="${REPO_URL:-https://github.com/zigamilek/ai-daily-journal.git}"
APP_REPO_REF="${REPO_REF:-master}"

CURRENT_STEP=""

log() {
  printf '[%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

fatal() {
  log "ERROR: $*"
  exit 1
}

on_error() {
  local line="$1"
  local command="$2"
  log "FAILED at line ${line}: ${command}"
  log "Hint: check journalctl -u ai-daily-journal.service and /var/log/ai-daily-journal/"
}
trap 'on_error "${LINENO}" "${BASH_COMMAND}"' ERR

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fatal "Run this installer as root."
  fi
}

install_packages() {
  CURRENT_STEP="install_packages"
  log "Installing OS dependencies"
  apt-get update -y
  apt-get install -y --no-install-recommends \
    ca-certificates curl git jq rsync \
    python3 python3-venv python3-pip python3-dev \
    build-essential libpq-dev \
    postgresql postgresql-contrib
}

install_pgvector() {
  CURRENT_STEP="install_pgvector"
  log "Ensuring pgvector extension is available"
  local pg_major pkg_name
  pg_major="$(psql --version | awk '{print $3}' | cut -d. -f1)"
  for pkg_name in "postgresql-${pg_major}-pgvector" "postgresql-pgvector"; do
    if apt-get install -y --no-install-recommends "${pkg_name}"; then
      log "Installed pgvector package: ${pkg_name}"
      return
    fi
  done
  log "pgvector package unavailable, building from source"
  apt-get install -y --no-install-recommends "postgresql-server-dev-${pg_major}" make gcc
  if ! getent hosts github.com >/dev/null 2>&1; then
    fatal "Cannot resolve github.com from container. Configure DNS/network and re-run installer."
  fi
  local tmpdir
  tmpdir="$(mktemp -d)"
  git clone --depth 1 https://github.com/pgvector/pgvector.git "${tmpdir}/pgvector" \
    || fatal "Failed to fetch pgvector source from GitHub. Check container network/firewall."
  make -C "${tmpdir}/pgvector"
  make -C "${tmpdir}/pgvector" install
  rm -rf "${tmpdir}"
}

ensure_user_and_dirs() {
  CURRENT_STEP="ensure_user_and_dirs"
  log "Creating service user and directories"
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
  fi
  install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0755 "${INSTALL_DIR}"
  install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0755 "${CONFIG_DIR}"
  install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0755 "${LOG_DIR}"
  install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0755 "${DATA_DIR}"
}

resolve_repo_source() {
  local script_path script_dir candidate tmp_repo
  script_path="${BASH_SOURCE[0]-}"
  if [[ -n "${script_path}" ]]; then
    script_dir="$(cd "$(dirname "${script_path}")" && pwd)"
    candidate="$(cd "${script_dir}/.." && pwd)"
    if [[ -f "${candidate}/pyproject.toml" ]]; then
      echo "${candidate}"
      return
    fi
  fi

  tmp_repo="/tmp/ai-daily-journal-src"
  rm -rf "${tmp_repo}"
  log "Installer running without local repo context; cloning ${APP_REPO_URL} (${APP_REPO_REF})" >&2
  if [[ -n "${APP_REPO_REF}" && "${APP_REPO_REF}" != "HEAD" ]]; then
    git clone --depth 1 --branch "${APP_REPO_REF}" "${APP_REPO_URL}" "${tmp_repo}"
  else
    git clone --depth 1 "${APP_REPO_URL}" "${tmp_repo}"
  fi
  echo "${tmp_repo}"
}

sync_repo() {
  CURRENT_STEP="sync_repo"
  local repo_src
  repo_src="$(resolve_repo_source)"
  if [[ ! -d "${repo_src}" ]]; then
    fatal "Resolved repository source directory does not exist: ${repo_src}"
  fi
  log "Syncing repository to ${INSTALL_DIR} from ${repo_src}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude '.git' "${repo_src}/" "${INSTALL_DIR}/"
  else
    cp -a "${repo_src}/." "${INSTALL_DIR}/"
  fi
  chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
}

setup_venv() {
  CURRENT_STEP="setup_venv"
  log "Setting up Python virtual environment"
  sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
  sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
  sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -e "${INSTALL_DIR}[dev]"
}

install_cli_symlink() {
  CURRENT_STEP="install_cli_symlink"
  log "Installing CLI symlink"
  ln -sf "${VENV_DIR}/bin/aijournal" /usr/local/bin/aijournal
}

set_env_key() {
  local key="$1" value="$2" file="$3"
  if grep -q "^${key}=" "${file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

write_default_config_non_destructive() {
  CURRENT_STEP="write_default_config_non_destructive"
  log "Generating default config and env (non-destructive)"

  if [[ ! -f "${CONFIG_FILE}" ]]; then
    cp "${INSTALL_DIR}/config.yaml.example" "${CONFIG_FILE}"
    sed -i "s|log_dir: \"./logs\"|log_dir: \"${LOG_DIR}\"|" "${CONFIG_FILE}"
    chown "${APP_USER}:${APP_GROUP}" "${CONFIG_FILE}"
  fi

  if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${INSTALL_DIR}/.env.example" "${ENV_FILE}"
    chown "${APP_USER}:${APP_GROUP}" "${ENV_FILE}"
    chmod 0640 "${ENV_FILE}"
  fi

  if [[ -z "${DB_PASSWORD}" ]]; then
    DB_PASSWORD="$(openssl rand -hex 16)"
  fi
  local db_url="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}"
  set_env_key "AI_DAILY_JOURNAL_DB_URL" "${db_url}" "${ENV_FILE}"

  if ! grep -q "^AI_DAILY_JOURNAL_SESSION_SECRET=" "${ENV_FILE}"; then
    set_env_key "AI_DAILY_JOURNAL_SESSION_SECRET" "$(openssl rand -hex 32)" "${ENV_FILE}"
  fi
}

setup_database() {
  CURRENT_STEP="setup_database"
  log "Configuring PostgreSQL database and role"
  systemctl enable --now postgresql
  sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
SQL

  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
  fi
  sudo -u postgres psql -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;"
}

run_migrations() {
  CURRENT_STEP="run_migrations"
  log "Running database migrations"
  sudo -u "${APP_USER}" env \
    AI_DAILY_JOURNAL_CONFIG="${CONFIG_FILE}" \
    AI_DAILY_JOURNAL_ENV="${ENV_FILE}" \
    "${VENV_DIR}/bin/alembic" -c "${INSTALL_DIR}/alembic.ini" upgrade head
}

install_systemd_unit() {
  CURRENT_STEP="install_systemd_unit"
  log "Installing systemd unit"
  cp "${INSTALL_DIR}/deploy/systemd/ai-daily-journal.service" "${SYSTEMD_UNIT_DEST}"
  chmod 0644 "${SYSTEMD_UNIT_DEST}"
  systemctl daemon-reload
  systemctl enable --now ai-daily-journal.service
}

health_check() {
  CURRENT_STEP="health_check"
  log "Running health check with retries"
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:8080/healthz" >/dev/null; then
      log "Health check passed"
      return
    fi
    sleep 2
  done
  systemctl status ai-daily-journal.service --no-pager || true
  journalctl -u ai-daily-journal.service -n 80 --no-pager || true
  fatal "Service failed health checks"
}

run_diagnostics() {
  CURRENT_STEP="run_diagnostics"
  log "Running diagnostics command"
  sudo -u "${APP_USER}" env \
    AI_DAILY_JOURNAL_CONFIG="${CONFIG_FILE}" \
    AI_DAILY_JOURNAL_ENV="${ENV_FILE}" \
    "${VENV_DIR}/bin/aijournal" diagnostics || true
}

print_summary() {
  cat <<EOF

AI Daily Journal installation complete.

- Service: ai-daily-journal.service
- Config: ${CONFIG_FILE}
- Env: ${ENV_FILE}
- App dir: ${INSTALL_DIR}
- Logs: ${LOG_DIR}
- Data dir: ${DATA_DIR}
- Health URL: http://127.0.0.1:8080/healthz

EOF
}

main() {
  require_root
  install_packages
  install_pgvector
  ensure_user_and_dirs
  sync_repo
  setup_venv
  install_cli_symlink
  write_default_config_non_destructive
  setup_database
  run_migrations
  install_systemd_unit
  health_check
  run_diagnostics
  print_summary
}

main "$@"
