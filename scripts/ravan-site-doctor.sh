#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${RAVAN_INSTALL_DIR:-/opt/ravan}"
JSON=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir) TARGET_DIR="${2:?missing value for --target-dir}"; shift 2 ;;
    --json) JSON=1; shift ;;
    -h|--help)
      echo "Usage: doctor.sh [--target-dir PATH] [--json]"
      exit 0
      ;;
    *) echo "Ravan doctor: unknown option $1" >&2; exit 2 ;;
  esac
done

[[ -f "$TARGET_DIR/.datastream/install.env" ]] || { echo "Ravan doctor: install metadata is missing" >&2; exit 1; }
source "$TARGET_DIR/.datastream/install.env"
command -v docker >/dev/null 2>&1 || { echo "Ravan doctor: Docker Engine is unavailable" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Ravan doctor: Docker Compose v2 is unavailable" >&2; exit 1; }

compose() {
  docker compose --project-name "$RAVAN_PROJECT_NAME" --env-file "$RAVAN_ENV_FILE" --file "$RAVAN_COMPOSE_FILE" --profile ui --profile edge "$@"
}

compose config --quiet
RUNNING="$(compose ps --status running --format '{{.Service}}' 2>/dev/null || true)"
SERVICE_STATE="$(systemctl is-active "${RAVAN_SERVICE_NAME}.service" 2>/dev/null || true)"
API_PORT="${API_SERVICE_HOST_PORT:-8020}"
DASHBOARD_PORT="${DASHBOARD_HOST_PORT:-3006}"
API_OK=0
DASHBOARD_OK=0
if command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && API_OK=1 || true
  curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:${DASHBOARD_PORT}/" >/dev/null 2>&1 && DASHBOARD_OK=1 || true
fi

if [[ "$JSON" -eq 1 ]]; then
  python3 - "$SERVICE_STATE" "$API_OK" "$DASHBOARD_OK" "$RUNNING" <<'PY'
import json
import sys
print(json.dumps({
    "service": sys.argv[1],
    "api_ok": sys.argv[2] == "1",
    "dashboard_ok": sys.argv[3] == "1",
    "running_services": [line for line in sys.argv[4].splitlines() if line],
}, indent=2))
PY
else
  echo "Ravan Site Server doctor"
  echo "========================"
  echo "service: ${SERVICE_STATE:-unknown}"
  echo "compose: valid"
  echo "api: $([[ "$API_OK" -eq 1 ]] && echo reachable || echo unavailable)"
  echo "dashboard: $([[ "$DASHBOARD_OK" -eq 1 ]] && echo reachable || echo unavailable)"
  echo
  echo "Running services:"
  printf '%s\n' "$RUNNING"
fi

if [[ "$SERVICE_STATE" != "active" || "$API_OK" -ne 1 || "$DASHBOARD_OK" -ne 1 ]]; then
  exit 1
fi
