# Release Packaging Checklist

This checklist is based on the current repository structure, not a generic industrial packaging template.

## 1. Package the actual runtime tree

Include the Python service tree that already exists in the repo:

- `services/api_service`
- `services/ai_gateway`
- `services/edge_ingest`
- `services/processor`
- `services/historian`
- `services/datasets`
- `services/scenarios`
- `services/federation`
- `services/analytics`
- `services/assets`
- `services/common`
- `services/cli`

Reason:

- the project already ships its runtime through `datastreamd`, `datastreamctl`, and `datastream-import`
- these packages contain the live API, streaming, historian, dataset, and benchmark logic

## 2. Include runtime assets that are already part of the structure

Bundle the non-code files that the runtime uses:

- `config/`
- `data/benchmarks/`
- `services/ingestion/debezium-postgres-orders.json`
- Dockerfiles under `services/`
- `docker/` compose files
- `scripts/` wrappers

Do not bundle:

- docs as runtime assets
- secrets
- generated `__pycache__`
- local benchmark outputs

## 3. Keep the operator surface aligned with the repo

The current installable tools are:

- `datastreamd`
- `datastreamctl`
- `datastream-import`

Packaging should preserve those entry points and make them available in the installer image or wheel-based runtime.

## 4. Windows package contents

Ship:

- runtime binaries or embedded Python runtime
- CLI entry points
- service registration files
- uninstall/rollback scripts
- site config templates
- logs/data/backups directories
- sample benchmark pack
- checksum and signature verification files
- optional launcher for the local UI

Do not require:

- WSL2
- Docker Desktop
- cloud credentials

The repo now includes a Windows staging path through `scripts/package-release.py` and `scripts/package-release.ps1`.

## 5. Linux package contents

Ship:

- runtime service
- CLI entry points
- systemd unit files
- install/uninstall scripts
- config templates
- sample benchmark pack
- local backup directories
- signature/checksum files
- optional Docker Compose demo helpers

Preferred targets:

- Ubuntu Server
- Debian
- other systemd-based Linux distributions

The repo now includes a Linux staging path through `scripts/package-release.py` and `scripts/package-release.sh`.

## 6. Offline and air-gapped package contents

Include:

- prebuilt dependency bundle
- sample datasets
- local diagnostics
- local benchmark runner
- package checksum file
- release signature file
- config templates
- site profile templates

Leave out:

- external SaaS dependencies
- mandatory online model endpoints

The repo now includes an offline staging path through `scripts/package-release.py` using the `offline` mode.

## 7. Structural changes to make packaging reliable

These are the repo-level changes that matter before a real release pipeline:

- package discovery must include the full `services.*` tree
- package data must include runtime JSON assets such as the Debezium connector config
- build artifacts such as `*.egg-info/`, `build/`, and `dist/` should remain ignored in the repo root
- installer docs must describe native Windows/Linux installs first
- release artifacts must stay separate from runtime installer assets
- benchmark reports must clearly label host profile and local-development results
- WSL2 must stay optional, not a dependency

## 8. Current state versus still needed

Already in place:

- CLI entry points
- runtime supervisor
- manifest export and release-package skeleton
- signed release skeleton
- backup drill reporting
- benchmark and calibration commands
- install guide
- repo-based packaging driver and OS shell wrappers
- Windows-native bundle export layout

Still needed for a full installer pipeline:

- final OS-specific installer generation
- package signing in the final installer format
- upgrade/uninstall automation
- smoke-test automation after install
- offline dependency bundle generation

## 9. Suggested release order

1. Fix build metadata and package discovery.
2. Ship native Linux/Windows install artifacts.
3. Add offline install bundle.
4. Add signed installer outputs.
5. Add upgrade and rollback automation.
6. Add optional desktop wrapper later if the market needs it.

## 10. Practical rule

If it is required to run the platform on a real host, it belongs in the package or the install workflow.

If it is a cloud secret, a site-specific credential, or a mutable production dependency, the operator owns it and provides it separately.
