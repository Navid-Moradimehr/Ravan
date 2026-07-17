#!/usr/bin/env bash
set -euo pipefail

NEW_COMPOSE=""
CURRENT_COMPOSE="${RAVAN_COMPOSE_FILE:-docker/docker-compose.yml}"
ROOT_DIR="${RAVAN_UPGRADE_DIR:-.datastream/upgrades}"
TIMEOUT_SECONDS="${RAVAN_UPGRADE_TIMEOUT:-120}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --compose-file) NEW_COMPOSE="$2"; shift 2 ;;
    --current-compose) CURRENT_COMPOSE="$2"; shift 2 ;;
    --upgrade-dir) ROOT_DIR="$2"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$NEW_COMPOSE" ]; then
  echo "usage: ravan-upgrade.sh --compose-file PATH [--current-compose PATH]" >&2
  exit 2
fi
command -v docker >/dev/null 2>&1 || { echo "Docker Engine is required" >&2; exit 1; }
[ -f "$NEW_COMPOSE" ] || { echo "new Compose file not found: $NEW_COMPOSE" >&2; exit 1; }
[ -f "$CURRENT_COMPOSE" ] || { echo "current Compose file not found: $CURRENT_COMPOSE" >&2; exit 1; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROOT_DIR/$STAMP"
BACKUP_COMPOSE="$ROOT_DIR/$STAMP/previous-compose.yml"
docker compose -f "$CURRENT_COMPOSE" config > "$BACKUP_COMPOSE"
docker compose -f "$NEW_COMPOSE" config --quiet
docker compose -f "$CURRENT_COMPOSE" ps > "$ROOT_DIR/$STAMP/previous-status.txt" || true

echo "Stopping current Ravan services without removing volumes..."
docker compose -f "$CURRENT_COMPOSE" stop
if docker compose -f "$NEW_COMPOSE" --profile ui --profile edge up -d; then
  deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    api="$(docker compose -f "$NEW_COMPOSE" ps api-service --status running --format '{{.Name}}' 2>/dev/null || true)"
    if [ -n "$api" ]; then
      echo "Upgrade started successfully. Rollback file: $BACKUP_COMPOSE"
      exit 0
    fi
    sleep 3
  done
fi

echo "Upgrade failed; stopping the new stack and restoring the previous Compose configuration." >&2
docker compose -f "$NEW_COMPOSE" stop || true
docker compose -f "$BACKUP_COMPOSE" --profile ui --profile edge up -d
echo "Rollback started from $BACKUP_COMPOSE" >&2
exit 1
