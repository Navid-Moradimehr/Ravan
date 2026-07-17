# Self-Hosted Install Guide

This guide describes the first practical install path for the open-source release.

## Goal

Install the platform so a company can run it inside its own network without giving the project cloud credentials or shared secrets.

## What ships

- `scripts/ravan.ps1` / `scripts/ravan.sh`: Docker Compose runtime wrapper
- `scripts/ravanctl.ps1` / `scripts/ravanctl.sh`: Docker-native operator CLI
- `datastreamd` and `datastreamctl`: optional Python source-developer tools
- `config/`: site and project configuration
- `data/`: sample benchmarks and replay packs
- `backups/`: local backup output

## Recommended install layout

Use a single site root per deployment:

```text
/opt/datastream/<project>/<site>/
  config/
  data/
  logs/
  models/
  backups/
```

On Windows, use a matching `C:\Datastream\<project>\<site>\` layout.

## Install flow

1. Install Docker Engine or Docker Desktop.
2. Copy `.env.production.example` to `.env`, replace every `CHANGE_ME` value, and set real broker, historian, and model endpoints.
3. Copy the project manifest and site profile into the site root.
4. Start Ravan with `./scripts/ravan.sh up -d` or `./scripts/ravan.ps1 up -d`.
5. Run `./scripts/ravanctl.sh doctor` or `./scripts/ravanctl.ps1 doctor`.
6. Run `./scripts/ravanctl.sh preflight` and review warnings.
7. Run `./scripts/ravanctl.sh status`.
8. Run a backup drill before connecting the site to federation or cross-site replication.

The Compose deployment uses restart policies and health checks for long-running
services. Migration and initialization containers intentionally stop after a
successful run; a stopped `timescaledb-migrate` or `kafka-init` container is
normal when its exit code is zero.

## Downtime handling

Do not configure a periodic reconnect timer in the UI or deployment package.
Connectors should retry automatically with protocol-appropriate backoff, and
operators should use the source enable/disable controls for planned outages.
If a maintenance window should be visible in health reporting, mark the source
or site as planned downtime in the operator-owned deployment state rather than
teaching the platform a company production calendar.

This keeps the platform portable across factories and utilities. The runtime
owns reconnect behavior; the operator owns maintenance schedules, outage
policy, and any external alert suppression rules.

Legacy historian deduplication is disabled by default so a restart does not
scan a large production historian. If an operator has evidence of legacy
duplicates, schedule maintenance, set `RUN_HISTORIAN_DEDUPE=true`, run the
one-shot migration, and verify the backup/release gate before returning to the
normal default.

## Docker production path

The Docker wrappers are the supported first-release operator path. They execute
the control CLI inside the running Ravan API container, so the operator machine
does **not** need Python, `pip`, or a project-local virtual environment.

Linux/macOS:

```bash
cp .env.production.example .env
# Replace development credentials and configure real endpoints in .env.
./scripts/ravan.sh up -d
./scripts/ravanctl.sh doctor
./scripts/ravanctl.sh preflight --strict
./scripts/ravanctl.sh status
```

Windows PowerShell:

```powershell
Copy-Item .env.production.example .env
# Replace development credentials and configure real endpoints in .env.
.\scripts\ravan.ps1 up -d
.\scripts\ravanctl.ps1 doctor
.\scripts\ravanctl.ps1 preflight --strict
.\scripts\ravanctl.ps1 status
```

`ravan` starts the UI and edge-ingest profiles but deliberately does not start
the OPC UA, MQTT, or Modbus simulators. Start a demo explicitly with
`docker compose -f docker/docker-compose.yml --profile demo --profile edge --profile ui up -d`.

## Python source-developer path

```bash
pip install -e .
datastreamd up --site-profile config/site-profiles/single-site.yaml
datastreamctl doctor
datastreamctl status
```

For systemd deployments:

```bash
datastreamctl project-manifest package config/project-manifest.yaml /tmp/datastream --site-id demo-site --format both --layout systemd
```

The generated systemd unit runs `datastreamd supervise` in the foreground. Do
not replace it with `datastreamd up`: `up` is a detached operator convenience
command, while `supervise` is the process owned by systemd or another service
manager. It writes child logs below the configured site runtime and applies a
bounded restart budget so a permanently broken service does not create an
unbounded restart storm.

For a release bundle, prefer the native staging target so the runtime source
tree is placed beside the generated site directory:

```bash
python3 scripts/package-release.py --output-dir dist --archive tar.gz linux
```

Extract the result and run the generated `systemd/install.sh` with `sudo`. It
creates a private `runtime/.venv`, installs the pinned Python requirements, and
registers the systemd unit. Set `RAVAN_SKIP_PIP_INSTALL=1` only when an
approved offline dependency installation has already been completed. Host
native mode still expects Kafka, TimescaleDB, Flink, and other infrastructure
to be supplied separately; use the Compose bundle for the complete single-host
stack.

The generated Linux uninstall is data-preserving by default. It stops and
removes the service unit but leaves the site directory, configuration, logs,
backups, and runtime data available for rollback. Pass `1` as the second
argument to the generated `systemd/uninstall.sh` only when the operator has
explicitly approved purging that site directory.

For Kubernetes deployments, use the Flink operator runbook at
[`docs/flink-operator-runbook.md`](docs/flink-operator-runbook.md) and the
local rehearsal guide at [`docs/local-kubernetes-rehearsal.md`](docs/local-kubernetes-rehearsal.md)
and the example deployment in `k8s/flink-operator/flinkdeployment.yaml`.
The `scripts/kind-rehearsal.ps1` helper can validate generated bundles before
you apply them to a real cluster.

## Windows example

Use the Docker production path above and keep the runtime rooted under a local directory that the operator controls.

Do not require WSL2 for the production install. If a team wants WSL2 for development or demos, treat it as an optional workstation convenience, not a bundled runtime dependency.

## Upgrade flow

1. Stop the runtime.
2. Export or verify the current package.
3. Save a local backup and checksum bundle.
4. Install the new version.
5. Restart with `ravan up -d`.
6. Re-run `ravanctl doctor` and the site-profile benchmark report.

The optional release notification does not install anything:

```bash
export DATASTREAM_UPDATE_CHECK_ENABLED=true
export DATASTREAM_UPDATE_MANIFEST_URL=https://github.com/OWNER/REPO/releases/latest/download/release-manifest.json
datastreamctl update check --manifest-url "$DATASTREAM_UPDATE_MANIFEST_URL"
```

The dashboard may show the same result as an in-app toast. Automatic download,
replacement, and rollback are deliberately deferred until the installer/update
agent exists. See [`docs/update-and-release-operations.md`](update-and-release-operations.md).

For a production deployment, do not reuse the Compose demo credentials or
floating demo endpoints. Supply operator-owned secrets and TLS/authentication
through the site's secret mechanism, then run the release gate and backup drill.
The development defaults remain available for local evaluation so upgrades do
not break existing users.

## What operators own

- broker endpoints
- historian endpoints
- model endpoints
- API keys or local auth tokens
- TLS materials
- backup destinations
- network placement

## What the platform owns

- runtime orchestration
- deterministic exports
- local benchmark/report generation
- backup/restore drill helpers
- protocol normalization and bridging contracts

## Why this is enough for the first release

The project should be installable before it is fully packaged. This guide gives integrators a repeatable path while the packaging story continues to mature.
