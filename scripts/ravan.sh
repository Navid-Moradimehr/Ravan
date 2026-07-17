#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine is required. Install and start Docker, then retry." >&2
  exit 1
fi

# Production starts Ravan UI and edge ingestion, but never demo protocol simulators.
exec docker compose -f docker/docker-compose.yml --profile ui --profile edge "$@"
