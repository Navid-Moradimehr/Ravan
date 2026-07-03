# Phase 8 Distribution Options

## Purpose

Phase 8 is the packaging and delivery phase for turning Local Stream Engine from a developer project into an installable open-source industrial tool.

The key decision is not only **how to package it**, but also **what kind of product users will install**:

- a local background service with CLI commands
- a terminal user interface
- a desktop application
- or a hybrid of the three

## Current Platform Reality

The platform already has these characteristics:

- Python backend services
- local Docker-based infrastructure
- Kafka-compatible streaming
- historian storage
- WebSocket-driven UI
- industrial simulation and replay workflows

That means Phase 8 should focus on **distribution and operations**, not a full rewrite.

## Distribution Goals

The installer strategy should satisfy these needs:

- simple installation on Windows and Linux first
- support for local and air-gapped environments
- predictable upgrades
- easy configuration and backup
- clear separation between runtime service and operator interface
- compatibility with industrial users who may prefer terminals, services, or local desktop tools over browser workflows

## Option A: Keep the Current Web UI and Package It Locally

### What it means

Ship the backend services plus a local launcher that starts the API and opens the existing UI locally.

### Pros

- fastest route to a distributable release
- reuses the current UI almost unchanged
- preserves existing operator workflows
- easy to keep feature parity with the current product

### Cons

- still feels web-based even if installed locally
- browser/runtime management can confuse some industrial users
- less aligned with a “native industrial tool” expectation

### Best fit

- early public open-source release
- demo distribution
- users who want the current dashboard immediately

## Option B: Desktop Application

### What it means

Wrap the operator interface in a desktop shell and ship native installers.

### Pros

- installer-based experience feels like a real product
- easier branding and product identity
- can manage config, logs, status, and updates from one shell
- good for operators who want GUI-first workflows

### Cons

- higher packaging complexity
- more moving parts for updates and support
- still requires deciding whether backend services are bundled or separately managed

### Best fit

- public open-source users
- pilot deployments
- teams expecting MSI/AppImage/DMG-style delivery

## Option C: Service + CLI + Terminal UI

### What it means

Package the platform primarily as a local service plus:

- `datastreamd` for the runtime
- `datastreamctl` for admin and replay commands
- optional Textual-style terminal UI for operators

### Pros

- most aligned with industrial and server-style deployment
- works well over SSH and in air-gapped setups
- easier to automate and script
- lighter than a desktop app

### Cons

- weaker visual experience than the current dashboard
- more design work needed for charts and rich interactions
- some current UI features would need TUI redesign

### Best fit

- plants and integrators
- edge installations
- environments where browser access is discouraged

## Option D: Recommended Hybrid

This is the recommended direction for this project.

### Shape of the product

- **Core runtime**: `datastreamd`
- **Admin CLI**: `datastreamctl`
- **Operator UI**:
  - short term: keep the current local web UI
  - medium term: add a desktop shell or TUI

### Why this is the best path

- it avoids rewriting the whole product at once
- it makes the runtime installable and scriptable
- it supports both developer users and industrial users
- it leaves room for either a TUI-first or desktop-first operator experience later

## Packaging Strategy

### Windows

- MSI installer for the runtime and tools
- optional service registration
- Start Menu shortcuts for logs, config, and operator UI

### Linux

- Debian package
- RPM package
- AppImage only if a desktop shell becomes part of the release
- systemd service unit for the runtime

### macOS

- lower priority unless a desktop release is desired
- possible later for developer/demo users

## Runtime Layout Recommendation

Install the product with a clear local structure:

- `bin/`
- `config/`
- `data/`
- `logs/`
- `models/`
- `backups/`

### Suggested components

- `datastreamd`: runtime supervisor for local services
- `datastreamctl`: command line administration
- `datastream-import`: dataset and replay import tool
- `datastream-doctor`: health and diagnostics tool

## Configuration Model

Configuration should support:

- single local YAML file for small installs
- environment overrides
- profiles such as `dev`, `demo`, `edge`, and `prod-like`
- export/import of configuration bundles

### Model Backend Compatibility

The AI gateway should stay provider-neutral so industrial users can connect the model stack they already operate.

The platform should support:

- OpenAI-compatible backends
- open-weight model servers such as vLLM, TGI, Ollama, llama.cpp, Triton, and custom HTTP wrappers
- local-only mode for air-gapped or plant-network deployments

The platform should own:

- request routing
- batch shaping
- response parsing
- fallback summaries when a model server is unavailable

Users should own:

- model weights
- GPU/CPU sizing
- endpoint URLs
- API keys or local auth tokens
- network placement inside their site or tenant boundary

This keeps the release compatible with local LLMs and future distributed inference without forcing one vendor.

## Upgrade Model

The safest upgrade path is:

1. stop runtime
2. snapshot config and local state
3. install new version
4. run migrations
5. restart services
6. verify health

Automatic updates should be optional and disabled by default in industrial environments.

## Open-Source Release Expectations

For open-source adoption, the release should include:

- install instructions
- quick-start profile
- offline install instructions
- sample config bundles
- sample datasets
- diagnostic commands
- contribution guide
- compatibility matrix for Windows and Linux

For the deployment recommendation and WSL2 guidance, see `docs/deployment-decision-memo.md`.

## Air-Gapped Support

This matters for industrial users.

Phase 8 should eventually include:

- offline dependency bundle
- container image export/import workflow
- local model configuration without cloud dependency
- local dataset packs
- no mandatory external SaaS dependency

## Multi-Site Rollout

For a company rolling this out across multiple plants or business units, the safest implementation path is:

1. standardize the runtime image and version across sites
2. keep a site-local broker, historian, and AI gateway per plant or region when latency or data sovereignty matters
3. centralize only the metadata or rollup layer if cross-site aggregation is needed
4. use configuration bundles per site so endpoints, models, and storage targets do not leak between locations
5. stage the rollout with one pilot line, then one plant, then a multi-site fleet
6. keep backups, replay packs, and model endpoints site-specific unless there is an explicit central platform team

This avoids turning one failed model server or broker into a company-wide outage.

See `docs/multi-site-rollout.md` for the full hardening checklist, rollout sequence, and release gates.

## Practical Recommendation

### Phase 8A

- package the runtime cleanly
- add `datastreamctl`
- formalize config, logs, and data directories
- ship Windows and Linux install flows
- keep the current UI as the first operator surface

### Phase 8B

- choose one operator experience:
  - desktop shell, or
  - terminal UI
- add backup/restore and diagnostics
- add signed releases and upgrade workflow

### Phase 8C

- add offline bundles
- harden packaging for edge and plant installs
- publish release channels and compatibility guarantees

## Recommendation Summary

If the goal is an installable industrial open-source tool and not only a browser app, the best move is:

- **Do not rewrite the product immediately**
- **Package the runtime first**
- **Add CLI/service structure first**
- **Keep the current UI temporarily**
- **Decide later between desktop shell and TUI based on target users**

For the AI path specifically:

- make the gateway work with OpenAI-compatible and open-weight backends from day one
- let users provide their own model servers and keys
- keep secure secrets out of the shared defaults
- ship local fallback behavior so ingest does not stall when inference is unavailable

That path is faster, safer, and better aligned with how industrial tools usually mature.

## Implemented Phase 8 Scaffolding (initial)

This section records the first concrete Phase 8 surface that is already in the repo, matching the hybrid recommendation above.

- `pyproject.toml`: project metadata, license, and the `datastreamctl` console-script entry point.
- `services/cli/datastreamctl.py`: operator control CLI. Subcommands:
  - `status`: live health of the API service and AI gateway.
  - `status-json`: same output as machine-readable JSON.
  - `scenarios`: lists the platform scenario catalog.
  - `datasets [--category]`: lists testing datasets from the runtime catalog.
  - `doctor`: runs reachability and import checks; returns non-zero on failure.
  - `config`: prints effective `DATASTREAM_API_BASE` / `DATASTREAM_AI_BASE` settings.
- `services/cli/__init__.py`: CLI package marker.
- `services/datasets/runtime_catalog.py`: single source of truth for dataset metadata mirrored from `docs/testing-data-catalog.md`.
- `tests/test_datastreamctl.py`: covers the runtime catalog and every CLI subcommand.

### Install / run

Install as a package (creates the `datastreamctl` command):

```bash
pip install -e .
datastreamctl status
datastreamctl datasets --category synthetic
datastreamctl doctor
```

Run without installing:

```bash
python -m services.cli.datastreamctl scenarios
```

For the operator install and upgrade path, see `docs/self-host-install-guide.md`.

### What this unlocks

- a scriptable, browser-free operator surface for industrial and SSH environments
- a reusable package boundary that future MSI/DEB/RPM/AppImage builders can target
- a clean place to add `datastreamd` (runtime supervisor) and `datastream-import` (dataset/replay importer) next

### Still ahead in Phase 8

- `datastreamd` runtime supervisor that starts/stops api_service, ai_gateway, edge ingest, and processor
- `datastream-import` dataset download/import adapter (AI4I, C-MAPSS first)
- platform installers (MSI for Windows, DEB/RPM for Linux) and systemd unit
- signed releases and optional auto-updater

## Implemented Phase 8 Scaffolding — runtime supervisor

`datastreamd` is now in the repo as the runtime supervisor described in the hybrid plan.

- `services/cli/datastreamd.py`: launches each platform service as a managed subprocess and tracks lifecycle via `.datastream/processes.json`.
- `services/cli/datastreamd.py` logs each service to `.datastream/logs/<service>.log`.
- `pyproject.toml`: adds the `datastreamd` console-script entry point.
- `tests/test_datastreamd.py`: covers service specs, dependency ordering, PID isolation, status, and clean shutdown.

### Managed services

| Name | Module | Role |
|------|--------|------|
| `api` | `services.api_service.main` | REST API + WebSocket streams (port 8020) |
| `ai` | `services.ai_gateway.main` | AI gateway / LLM enrichment (port 8080) |
| `edge` | `services.edge_ingest.main` | Protocol ingestion: OPC UA, MQTT, Modbus |
| `processor` | `services.processor.runtime_processor` | Stream processing and anomaly scoring |
| `mock` | `services.datasets.mock_generator` | Mock industrial data generator |

`datastreamd` manages the Python services only. Docker infrastructure (Redpanda, Postgres/TimescaleDB, Grafana, Prometheus) still runs through `docker compose` as before.

### Commands

```bash
datastreamd up                    # start all managed services
datastreamd up --only api,ai      # start a subset
datastreamd up --only api --wait 12  # start and wait for health
datastreamd status                # show UP/DOWN per service
datastreamd down                  # stop all managed services
datastreamd down --only edge      # stop a subset
datastreamd restart api,ai        # restart services (preserves order)
datastreamd logs api -n 50        # tail a service log
```

### Verified

- Full Python suite: 113 passed (was 105).
- `datastreamd status` runs and reports all five services.
- `datastreamd up --only api` launches the API subprocess, records its PID, writes a per-service log, and `down` stops it. The API exited with a historian import error in this environment because the TimescaleDB backend is not running, which is expected — the supervisor correctly captured the failure in `logs/api.log` rather than masking it.

### Prerequisites for a full `up`

Before `datastreamd up` will keep services UP:

1. `docker compose -f docker/docker-compose.yml up -d` for Redpanda, Postgres/TimescaleDB, Grafana.
2. `scripts/create-industrial-topics.ps1` (or `.sh`) to create Kafka topics.
3. A valid `.env` copied from `.env.example`.
