#!/usr/bin/env bash
set -Eeuo pipefail

BUNDLES="${RAVAN_OPERATOR_BUNDLES:-dmg}"
OUTPUT_DIR="${RAVAN_OPERATOR_OUTPUT_DIR:-dist/operator-installer}"
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPERATOR_ROOT="$REPO_ROOT/operator-shell"
BUNDLE_ROOT="$OPERATOR_ROOT/src-tauri/target/release/bundle"

command -v node >/dev/null 2>&1 || { echo "Node.js 20+ is required" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 1; }
command -v cargo >/dev/null 2>&1 || { echo "Rust/Cargo is required" >&2; exit 1; }

rm -rf "$BUNDLE_ROOT"

cd "$OPERATOR_ROOT"
npm ci
npm run tauri -- build --bundles "$BUNDLES" --ci
[[ -d "$BUNDLE_ROOT" ]] || { echo "Tauri did not produce bundle output: $BUNDLE_ROOT" >&2; exit 1; }
mkdir -p "$REPO_ROOT/$OUTPUT_DIR"
find "$BUNDLE_ROOT" -type f \( -name '*.exe' -o -name '*.msi' -o -name '*.dmg' -o -name '*.appimage' -o -name '*.deb' -o -name '*.rpm' \) -exec cp -f {} "$REPO_ROOT/$OUTPUT_DIR/" \;
echo "Operator installers copied to $REPO_ROOT/$OUTPUT_DIR"
