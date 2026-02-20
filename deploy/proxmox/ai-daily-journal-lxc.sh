#!/usr/bin/env bash
source <(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/misc/build.func)
# Copyright (c) 2021-2026 community-scripts ORG
# Author: community-scripts contributors
# Maintainer: zigamilek
# License: MIT | https://github.com/community-scripts/ProxmoxVE/raw/main/LICENSE
# Source: https://github.com/zigamilek/ai-daily-journal

APP="AI Daily Journal"
var_tags="${var_tags:-ai-daily-journal;journal;llm}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-2048}"
var_disk="${var_disk:-12}"
var_os="${var_os:-debian}"
var_version="${var_version:-12}"
var_unprivileged="${var_unprivileged:-1}"
var_gpu="${var_gpu:-no}"
JOURNAL_REPO_URL="${REPO_URL:-https://github.com/zigamilek/ai-daily-journal.git}"
JOURNAL_REPO_REF="${REPO_REF:-master}"
JOURNAL_RAW_REPO_PATH="${RAW_REPO_PATH:-zigamilek/ai-daily-journal}"
JOURNAL_INSTALLER_URL="https://raw.githubusercontent.com/${JOURNAL_RAW_REPO_PATH}/${JOURNAL_REPO_REF}/install/ai-daily-journal-install.sh"

header_info "$APP"
variables
color
catch_errors

# Keep the full tteck/container-build lifecycle, but replace only the final
# app installer URL with this project's install script.
curl() {
 local target="https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/install/${var_install}.sh"
 local args=()
 local replaced=0
 for arg in "$@"; do
 if [[ "$arg" == "$target" ]]; then
 args+=("$JOURNAL_INSTALLER_URL")
 replaced=1
 else
 args+=("$arg")
 fi
 done
 if [[ "$replaced" -eq 1 ]]; then
 msg_info "Using project installer: ${JOURNAL_INSTALLER_URL}"
 fi
 command curl "${args[@]}"
}

function update_script() {
 header_info
 check_container_storage
 check_container_resources

 if [[ "${VERBOSE:-no}" == "yes" ]]; then
 msg_info "Verbose mode enabled: showing command output (xtrace disabled)."
 fi

 local APP_DIR="/opt/ai-daily-journal"
 local CONFIG_DIR="/etc/ai-daily-journal"
 local SERVICE_NAME="ai-daily-journal"
 local SERVICE_USER="ai-daily-journal"
 local REPO_URL="${REPO_URL:-$JOURNAL_REPO_URL}"
 local REPO_REF="${REPO_REF:-$JOURNAL_REPO_REF}"
 local GIT_SAFE_ARGS=(-c "safe.directory=${APP_DIR}")

 detect_service_port() {
 local config_file="${CONFIG_DIR}/config.yaml"
 local parsed=""
 if [[ -f "${config_file}" ]]; then
 parsed="$(
 awk '
 /^[[:space:]]*server:[[:space:]]*$/ { in_server=1; next }
 in_server && /^[^[:space:]]/ { in_server=0 }
 in_server && /^[[:space:]]*port:[[:space:]]*[0-9]+[[:space:]]*$/ {
 line = $0
 sub(/^[[:space:]]*port:[[:space:]]*/, "", line)
 sub(/[[:space:]]*$/, "", line)
 print line
 exit
 }
 ' "${config_file}" 2>/dev/null || true
 )"
 fi
 if [[ "${parsed}" =~ ^[0-9]+$ ]]; then
 echo "${parsed}"
 else
 echo "8080"
 fi
 }

 verify_service_start() {
 local service_name="$1"
 local port
 local health_url
 local i

 if ! systemctl is-active --quiet "${service_name}"; then
 msg_error "${service_name} is not active after startup."
 systemctl status "${service_name}" --no-pager || true
 journalctl -u "${service_name}" -n 120 --no-pager || true
 return 1
 fi

 port="$(detect_service_port)"
 health_url="http://127.0.0.1:${port}/healthz"
 for i in {1..20}; do
 if curl -fsS --max-time 2 "${health_url}" >/dev/null 2>&1; then
 msg_ok "Service health check passed: ${health_url}"
 return 0
 fi
 sleep 1
 done

 msg_error "Service failed health checks: ${health_url}"
 systemctl status "${service_name}" --no-pager || true
 journalctl -u "${service_name}" -n 120 --no-pager || true
 return 1
 }

 msg_info "Stopping ${SERVICE_NAME} service"
 $STD systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
 msg_ok "Stopped ${SERVICE_NAME} service"

 msg_info "Installing/updating OS dependencies"
 $STD apt-get update
 $STD apt-get install -y git python3 python3-venv python3-pip rsync ca-certificates curl
 msg_ok "Dependencies installed"

 msg_info "Ensuring service user exists"
 if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
 useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin "${SERVICE_USER}"
 fi
 msg_ok "Service user ready"

 msg_info "Updating repository"
 if [[ ! -d "${APP_DIR}/.git" ]]; then
 $STD rm -rf "${APP_DIR}"
 if [[ -n "${REPO_REF}" && "${REPO_REF}" != "HEAD" ]]; then
 $STD git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" "${APP_DIR}"
 else
 $STD git clone --depth 1 "${REPO_URL}" "${APP_DIR}"
 fi
 else
 pushd "${APP_DIR}" >/dev/null
 if [[ -n "${REPO_REF}" && "${REPO_REF}" != "HEAD" ]]; then
 $STD git "${GIT_SAFE_ARGS[@]}" fetch origin "${REPO_REF}"
 $STD git "${GIT_SAFE_ARGS[@]}" checkout "${REPO_REF}"
 $STD git "${GIT_SAFE_ARGS[@]}" pull --ff-only origin "${REPO_REF}"
 else
 $STD git "${GIT_SAFE_ARGS[@]}" pull --ff-only
 fi
 popd >/dev/null
 fi
 msg_ok "Repository updated"

 msg_info "Rebuilding Python environment"
 $STD python3 -m venv "${APP_DIR}/.venv"
 $STD "${APP_DIR}/.venv/bin/pip" install --upgrade pip
 $STD "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}[dev]"
 msg_ok "Python environment ready"

 msg_info "Installing CLI command symlinks"
 $STD ln -sf "${APP_DIR}/.venv/bin/aijournal" /usr/local/bin/aijournal
 msg_ok "CLI command available: aijournal"

 msg_info "Refreshing runtime files"
 $STD mkdir -p "${CONFIG_DIR}" "${CONFIG_DIR}/prompts" /var/log/ai-daily-journal /var/lib/ai-daily-journal
 [[ -f "${CONFIG_DIR}/config.yaml" ]] || $STD cp "${APP_DIR}/config.yaml.example" "${CONFIG_DIR}/config.yaml"
 [[ -f "${CONFIG_DIR}/.env" ]] || $STD cp "${APP_DIR}/.env.example" "${CONFIG_DIR}/.env"
 $STD chmod 640 "${CONFIG_DIR}/.env"
 for prompt_file in "${APP_DIR}/prompts/"*.md; do
 prompt_name="$(basename "${prompt_file}")"
 [[ -f "${CONFIG_DIR}/prompts/${prompt_name}" ]] || $STD cp "${prompt_file}" "${CONFIG_DIR}/prompts/${prompt_name}"
 done
 $STD cp "${APP_DIR}/deploy/systemd/ai-daily-journal.service" "/etc/systemd/system/${SERVICE_NAME}.service"
 $STD chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}" "${CONFIG_DIR}" /var/log/ai-daily-journal /var/lib/ai-daily-journal
 msg_ok "Runtime files refreshed"

 msg_info "Running database migrations"
 $STD env \
 AI_DAILY_JOURNAL_CONFIG="${CONFIG_DIR}/config.yaml" \
 AI_DAILY_JOURNAL_ENV="${CONFIG_DIR}/.env" \
 "${APP_DIR}/.venv/bin/alembic" -c "${APP_DIR}/alembic.ini" upgrade head
 msg_ok "Migrations applied"

 msg_info "Restarting ${SERVICE_NAME}"
 $STD systemctl daemon-reload
 $STD systemctl enable -q --now "${SERVICE_NAME}"
 verify_service_start "${SERVICE_NAME}"
 msg_ok "Updated successfully"

 msg_ok "Use 'aijournal onboarding' to update env/config interactively."
 exit
}

start
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW} Access it using the following URL:${CL}"
echo -e "${TAB}${GATEWAY}${BGN}http://${IP}:8080${CL}"
