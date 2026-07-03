#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/package-release.py"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_PATH" "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$SCRIPT_PATH" "$@"
fi

echo "python3 or python is required to run package-release.sh" >&2
exit 1
