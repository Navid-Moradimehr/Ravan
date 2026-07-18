#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Engine is required. Install and start Docker, then retry." >&2
  exit 1
fi

COMPOSE_FILE="${RAVAN_COMPOSE_FILE:-docker/docker-compose.yml}"

if ! docker compose -f "${COMPOSE_FILE}" ps api-service --status running --format '{{.Name}}' >/dev/null; then
  echo "The Ravan API service is not running. Start the stack first: ./scripts/ravan.sh up" >&2
  exit 1
fi

if [ "${1:-}" = "preflight" ]; then
  shift
  preflight_args="preflight --compose-file /workspace/${COMPOSE_FILE#./} --site-profile /workspace/config/site-profiles/single-site.yaml --project-manifest /workspace/config/project-manifest.yaml"
  if [ -f .env ]; then
    preflight_args="$preflight_args --env-file /workspace/.env"
  fi
  exec docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T \
    -v "$(pwd):/workspace:ro" -w /workspace api-service \
    sh -c "python -m services.cli.datastreamctl $preflight_args \"\$@\"" sh "$@"
fi

exec docker compose -f "${COMPOSE_FILE}" exec -T api-service python -m services.cli.datastreamctl "$@"
