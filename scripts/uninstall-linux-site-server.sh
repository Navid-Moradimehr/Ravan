#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${RAVAN_INSTALL_DIR:-/opt/ravan}"
PURGE=0
YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir) TARGET_DIR="${2:?missing value for --target-dir}"; shift 2 ;;
    --purge) PURGE=1; shift ;;
    --yes) YES=1; shift ;;
    -h|--help)
      echo "Usage: uninstall.sh [--target-dir PATH] [--purge --yes]"
      exit 0
      ;;
    *) echo "Ravan uninstall: unknown option $1" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || { echo "run as root or install sudo" >&2; exit 1; }
  exec sudo -E bash "$0" "$@"
fi

[[ -f "$TARGET_DIR/.datastream/install.env" ]] || { echo "Ravan uninstall: install metadata is missing" >&2; exit 1; }
source "$TARGET_DIR/.datastream/install.env"

if [[ -f "/etc/systemd/system/${RAVAN_SERVICE_NAME}.service" ]]; then
  systemctl stop "${RAVAN_SERVICE_NAME}.service" || true
  systemctl disable "${RAVAN_SERVICE_NAME}.service" >/dev/null 2>&1 || true
  rm -f "/etc/systemd/system/${RAVAN_SERVICE_NAME}.service"
  systemctl daemon-reload
fi

# Stop containers but never remove named volumes implicitly. Historian, Kafka,
# and object-storage data must remain recoverable after an application removal.
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose --project-name "$RAVAN_PROJECT_NAME" --env-file "$RAVAN_ENV_FILE" --file "$RAVAN_COMPOSE_FILE" --profile ui --profile edge stop || true
fi

if [[ "$PURGE" -eq 0 ]]; then
  echo "Ravan service removed. Data and configuration preserved at ${TARGET_DIR}."
  echo "Named Docker volumes were not removed."
  exit 0
fi

[[ "$YES" -eq 1 ]] || { echo "--purge deletes the install directory; add --yes to confirm" >&2; exit 2; }
case "$TARGET_DIR" in
  /|/opt|/usr|/var|/home|/root|/tmp) echo "refusing to purge unsafe target: $TARGET_DIR" >&2; exit 1 ;;
esac
rm -rf -- "$TARGET_DIR"
echo "Ravan install directory purged: ${TARGET_DIR}"
echo "Named Docker volumes were not removed; remove them separately only after a verified backup."
