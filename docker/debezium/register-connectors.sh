#!/usr/bin/env bash
# Register Debezium CDC connectors with the Kafka Connect REST API.
#
# Usage:
#   docker/debezium/register-connectors.sh [connect-url]
#
# Default connect URL targets the compose 'connect' service on port 18083.
# Re-running is safe: existing connectors are deleted before re-registration
# so the config in this repo is the source of truth.
set -euo pipefail

CONNECT_URL="${1:-http://localhost:18083}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for cfg in "$SCRIPT_DIR"/*.json; do
  name="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['name'])" "$cfg")"
  echo "==> Registering connector '$name' from $cfg"
  # Best-effort delete (ignore failure if it doesn't exist yet).
  curl -fsS -X DELETE "$CONNECT_URL/connectors/$name" >/dev/null 2>&1 || true
  # Register with the new config.
  curl -fsS -X POST "$CONNECT_URL/connectors" \
    -H 'Content-Type: application/json' \
    -d @"$cfg" | python3 -m json.tool
  echo
done

echo "==> Registered connectors:"
curl -fsS "$CONNECT_URL/connectors" | python3 -m json.tool
