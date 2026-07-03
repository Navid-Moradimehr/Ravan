# Production Hardening Checklist - 2026-07-03

## Focus

- multi-site rollout
- self-hosted security
- packaging later
- realistic simulator and benchmarks

## In Progress

- manifest/site identity validation gap
- execution checklist capture

## Remaining

- target-hardware benchmark validation
- target-hardware sizing validation
- restore/rollback drill measurement across at least two sites

## Notes

- Keep raw plant data local by default.
- Federation should only consume approved rollups or explicit bridge outputs.
- Packaging remains deferred until runtime and deployment shape are stable.
- The simulator now needs to be compared with repeated benchmark sessions, not one-off local runs.
- Operators should inject JWT, broker, historian, and model secrets from their own secret store.
- backup drills now capture before/after historian snapshots and compare row counts
- release-package can emit `release-signature.json` when the operator supplies a signing key
- site-profile matrix/calibration benchmarks can export report directories for archiving
- benchmark report exports now include host-profile metadata for local-vs-target separation
- self-host install guidance is documented for Linux and Windows operators
- WSL2 is now explicitly treated as a developer convenience, not a production dependency
- packaging checklist is now tied to the actual repo structure and build metadata
- packaging driver scripts now stage Windows, Linux, and offline bundles from the real repo tree
- Windows bundle export now exists as a first-class manifest layout
- rollout acceptance report export is now available for archiveable per-site runs
- the simulator now includes multi-PLC, burst, and reconnect cases
- self-hosted secrets guidance is already documented for Docker, systemd, and Kubernetes
- packaging driver scripts now stage Windows, Linux, and offline bundles from the real repo tree
- Windows bundle export now exists as a first-class manifest layout

## Measured Baseline

- `multi-plc-line`: 93,307.08 events/sec
- `burst-load`: 90,183.52 events/sec
- `dropout-reconnect`: 95,832.26 events/sec
- `industrial-benchmark`: 94,157.53 events/sec
- average: 93,370.10 events/sec

## Repeat Matrix

- `demo-site`: mean 86,376.50 events/sec, median 86,376.50, stdev 288.99, repeats 2
- `plant-a`: mean 94,552.48 events/sec, median 94,552.48, stdev 1,214.24, repeats 2
- `demo-site`: mean 90,392.42 events/sec, median 90,392.42, stdev 6,175.55, repeats 2
- `plant-a`: mean 92,189.32 events/sec, median 92,189.32, stdev 1,804.84, repeats 2

## Release Skeleton

- release-package command now emits `release-manifest.json` and `checksums.sha256`
- release-package can optionally emit `release-signature.json`
- package output stays separate from future signed release artifacts

## Packaging Driver

- `scripts/package-release.py` stages the actual repo tree into release-ready runtime bundles.
- `scripts/package-release.ps1` and `scripts/package-release.sh` are thin wrappers for Windows and Linux operators.
- Windows layout exports native `install.ps1`, `uninstall.ps1`, `.cmd` launchers, and a Windows-specific README.

## Install Guide

- `docs/self-host-install-guide.md` now covers the local install, upgrade, and operator-owned secret model.
- `docs/deployment-decision-memo.md` records the native Windows/Linux recommendation and the WSL2 boundary.
- `docs/release-packaging-checklist.md` maps package contents to the services tree, config, data, and entry points.

## Build Metadata

- `pyproject.toml` now discovers the full `services.*` tree for distributable builds.
- runtime JSON assets under `services/ingestion` are included as package data.
- `*.egg-info/` is ignored so packaging checks do not clutter the repo root.

## Packaging Driver

- `scripts/package-release.py` stages the repo-based bundles.
- `scripts/package-release.ps1` and `scripts/package-release.sh` are thin wrappers for Windows and Linux operators.
