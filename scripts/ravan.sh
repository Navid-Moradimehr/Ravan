#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine is required. Install and start Docker, then retry." >&2
  exit 1
fi

# Production starts Ravan UI and edge ingestion, but never demo protocol simulators.
COMPOSE_FILE="${RAVAN_COMPOSE_FILE:-docker/docker-compose.yml}"
exec docker compose -f "${COMPOSE_FILE}" --profile ui --profile edge "$@"
