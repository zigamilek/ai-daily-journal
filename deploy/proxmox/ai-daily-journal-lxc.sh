#!/usr/bin/env bash
set -Eeuo pipefail

CTID="${CTID:-216}"
HOSTNAME="${HOSTNAME:-ai-daily-journal}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"
CONTAINER_STORAGE="${CONTAINER_STORAGE:-local-lvm}"
TEMPLATE_NAME="${TEMPLATE_NAME:-debian-12-standard_12.7-1_amd64.tar.zst}"
BRIDGE="${BRIDGE:-vmbr0}"
DISK_SIZE="${DISK_SIZE:-12}"
CORES="${CORES:-2}"
MEMORY="${MEMORY:-2048}"
SWAP="${SWAP:-512}"
APP_REPO="${APP_REPO:-https://github.com/zigamilek/ai-daily-journal.git}"
APP_BRANCH="${APP_BRANCH:-master}"
UNPRIVILEGED="${UNPRIVILEGED:-1}"

log() {
  printf '[%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

require_root() {
  [[ "$EUID" -eq 0 ]] || die "Run this script as root on Proxmox host."
}

validate_host() {
  require_root
  require_cmd pct
  require_cmd pveam
}

ensure_template() {
  log "Ensuring Debian 12 template exists"
  if ! pveam list "${TEMPLATE_STORAGE}" | awk '{print $2}' | grep -q "^${TEMPLATE_NAME}$"; then
    log "Downloading template ${TEMPLATE_NAME}"
    pveam update
    pveam download "${TEMPLATE_STORAGE}" "${TEMPLATE_NAME}"
  fi
}

create_container() {
  if pct status "${CTID}" >/dev/null 2>&1; then
    die "Container CTID ${CTID} already exists. Set CTID to another value."
  fi

  local rootfs="${CONTAINER_STORAGE}:${DISK_SIZE}"
  local net0="name=eth0,bridge=${BRIDGE},ip=dhcp"

  log "Creating LXC ${CTID} (${HOSTNAME})"
  pct create "${CTID}" "${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE_NAME}" \
    --hostname "${HOSTNAME}" \
    --cores "${CORES}" \
    --memory "${MEMORY}" \
    --swap "${SWAP}" \
    --rootfs "${rootfs}" \
    --net0 "${net0}" \
    --unprivileged "${UNPRIVILEGED}" \
    --features keyctl=1,nesting=1 \
    --onboot 1
}

bootstrap_container() {
  log "Starting container ${CTID}"
  pct start "${CTID}"
  sleep 3

  log "Installing bootstrap packages in container"
  pct exec "${CTID}" -- bash -lc "apt-get update -y && apt-get install -y git curl rsync sudo"
}

install_app() {
  log "Cloning repository ${APP_REPO} (branch ${APP_BRANCH}) inside container"
  pct exec "${CTID}" -- bash -lc "rm -rf /opt/ai-daily-journal-src"
  pct exec "${CTID}" -- bash -lc "git clone --depth 1 --branch '${APP_BRANCH}' '${APP_REPO}' /opt/ai-daily-journal-src"

  log "Running in-container installer"
  pct exec "${CTID}" -- bash -lc "cd /opt/ai-daily-journal-src && bash install/ai-daily-journal-install.sh"
}

print_summary() {
  local ip
  ip="$(pct exec "${CTID}" -- bash -lc "hostname -I | awk '{print \$1}'" | tr -d '\r' || true)"
  cat <<EOF

AI Daily Journal LXC deployment finished.

- CTID: ${CTID}
- Hostname: ${HOSTNAME}
- Repo: ${APP_REPO} (${APP_BRANCH})
- Container IP: ${ip:-unknown}
- Health URL: http://${ip:-<container-ip>}:8080/healthz
- Service status:
$(pct exec "${CTID}" -- systemctl is-active ai-daily-journal.service || true)

EOF
}

main() {
  validate_host
  ensure_template
  create_container
  bootstrap_container
  install_app
  print_summary
}

main "$@"
