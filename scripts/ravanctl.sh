#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine is required. Install and start Docker, then retry." >&2
  exit 1
fi

if ! docker compose -f docker/docker-compose.yml ps api-service --status running --format '{{.Name}}' >/dev/null; then
  echo "The Ravan API service is not running. Start the stack first: ./scripts/ravan.sh up" >&2
  exit 1
fi

exec docker compose -f docker/docker-compose.yml exec -T api-service python -m services.cli.datastreamctl "$@"
