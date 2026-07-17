#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${RAVAN_INSTALL_DIR:-/opt/ravan}"
MODE=""
TIMEOUT_SECONDS="${RAVAN_UPGRADE_TIMEOUT:-180}"
BUNDLE_DIR=""

usage() {
  echo "Usage: upgrade.sh --bundle-dir PATH [--mode source-build|registry] [--target-dir PATH] [--timeout SECONDS]"
}

die() { echo "Ravan upgrade: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle-dir) BUNDLE_DIR="${2:?missing value for --bundle-dir}"; shift 2 ;;
    --mode) MODE="${2:?missing value for --mode}"; shift 2 ;;
    --target-dir) TARGET_DIR="${2:?missing value for --target-dir}"; shift 2 ;;
    --timeout) TIMEOUT_SECONDS="${2:?missing value for --timeout}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ -n "$BUNDLE_DIR" ]] || { usage >&2; exit 2; }
[[ -d "$BUNDLE_DIR/runtime/docker" ]] || die "new bundle does not contain runtime/docker"
[[ -f "$TARGET_DIR/.datastream/install.env" ]] || die "current installation metadata is missing"
[[ -n "$MODE" ]] || MODE="$(grep '^RAVAN_INSTALL_MODE=' "$TARGET_DIR/.datastream/install.env" | cut -d= -f2- | tr -d "'\"")"
[[ "$MODE" == "source-build" || "$MODE" == "registry" ]] || die "mode must be source-build or registry"

if [[ "$(id -u)" -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || die "run as root or install sudo"
  exec sudo -E bash "$0" "$@"
fi

command -v docker >/dev/null 2>&1 || die "Docker Engine is required"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 plugin is required"
source "$TARGET_DIR/.datastream/install.env"

rollback() {
  echo "Ravan upgrade failed; restoring the previous runtime." >&2
  "$TARGET_DIR/bin/compose.sh" stop || true
  systemctl stop "${RAVAN_SERVICE_NAME}.service" || true
  rm -rf "$TARGET_DIR/runtime"
  mv "$TARGET_DIR/runtime.previous" "$TARGET_DIR/runtime"
  cp "$UPGRADE_DIR/previous-install.env" "$TARGET_DIR/.datastream/install.env"
  if [[ -f "$UPGRADE_DIR/previous.service" ]]; then
    cp "$UPGRADE_DIR/previous.service" "/etc/systemd/system/${RAVAN_SERVICE_NAME}.service"
  fi
  systemctl daemon-reload
  systemctl start "${RAVAN_SERVICE_NAME}.service" || true
  echo "Rollback started. Evidence: $UPGRADE_DIR" >&2
}

NEW_COMPOSE="$BUNDLE_DIR/runtime/docker/docker-compose.yml"
if [[ "$MODE" == "registry" ]]; then
  NEW_COMPOSE="$BUNDLE_DIR/runtime/docker/docker-compose.release.yml"
fi
[[ -f "$NEW_COMPOSE" ]] || die "new Compose file is missing: $NEW_COMPOSE"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
UPGRADE_DIR="$TARGET_DIR/.datastream/upgrades/$STAMP"
mkdir -p "$UPGRADE_DIR"
cp -a "$TARGET_DIR/runtime" "$UPGRADE_DIR/previous-runtime"
cp "$TARGET_DIR/.datastream/install.env" "$UPGRADE_DIR/previous-install.env"
cp "/etc/systemd/system/${RAVAN_SERVICE_NAME}.service" "$UPGRADE_DIR/previous.service" 2>/dev/null || true

NEW_RUNTIME="$TARGET_DIR/runtime.next"
rm -rf "$NEW_RUNTIME"
cp -a "$BUNDLE_DIR/runtime" "$NEW_RUNTIME"
NEW_COMPOSE="$NEW_RUNTIME/docker/$(basename "$NEW_COMPOSE")"

compose_new() {
  docker compose --project-name "$RAVAN_PROJECT_NAME" --env-file "$RAVAN_ENV_FILE" --file "$NEW_COMPOSE" --profile ui --profile edge "$@"
}

compose_new config --quiet || die "new Compose configuration is invalid"
"$TARGET_DIR/bin/compose.sh" stop || true
systemctl stop "${RAVAN_SERVICE_NAME}.service" || true

rm -rf "$TARGET_DIR/runtime.previous"
mv "$TARGET_DIR/runtime" "$TARGET_DIR/runtime.previous"
mv "$NEW_RUNTIME" "$TARGET_DIR/runtime"

cat > "$TARGET_DIR/.datastream/install.env" <<EOF
RAVAN_INSTALL_DIR=$(printf '%q' "$TARGET_DIR")
RAVAN_SITE_ID=$(printf '%q' "$RAVAN_SITE_ID")
RAVAN_INSTALL_MODE=$(printf '%q' "$MODE")
RAVAN_SERVICE_NAME=$(printf '%q' "$RAVAN_SERVICE_NAME")
RAVAN_PROJECT_NAME=$(printf '%q' "$RAVAN_PROJECT_NAME")
RAVAN_ENV_FILE=$(printf '%q' "$RAVAN_ENV_FILE")
RAVAN_COMPOSE_FILE=$(printf '%q' "$TARGET_DIR/runtime/docker/$(basename "$NEW_COMPOSE")")
EOF

if [[ "$MODE" == "registry" ]]; then
  if ! "$TARGET_DIR/bin/compose.sh" pull; then
    rollback
    exit 1
  fi
else
  if ! "$TARGET_DIR/bin/compose.sh" build; then
    rollback
    exit 1
  fi
fi

systemctl daemon-reload
if ! systemctl start "${RAVAN_SERVICE_NAME}.service"; then
  rollback
  exit 1
fi
deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
while [[ "$(date +%s)" -lt "$deadline" ]]; do
  if "$TARGET_DIR/bin/doctor.sh" >/dev/null 2>&1; then
    echo "Ravan upgrade succeeded. Evidence: $UPGRADE_DIR"
    rm -rf "$TARGET_DIR/runtime.previous"
    exit 0
  fi
  sleep 3
done

rollback
exit 1
