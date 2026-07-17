# Installation Options And Requirements

This document defines the intended installation products and the operator work
required after installation. It separates the platform runtime from optional
AI, lakehouse, and enterprise infrastructure so hardware requirements are not
overstated.

## Product Packages

The project should publish these product packages rather than a separate
installer for every feature:

| Package | Target | Role |
|---|---|---|
| Compose Site Bundle | Linux, Windows, macOS with Docker | Supported first-release complete single-site runtime |
| Site Server | Linux x86-64 | Future host-native complete single-site runtime |
| Edge Collector | Linux x86-64 and ARM64 | Collection and store-and-forward near equipment |
| Windows Full Node | Windows x64 | Future complete local runtime through a managed Linux appliance |
| Windows Operator | Windows x64 | Desktop client for a local or remote runtime |
| macOS Operator | macOS universal | Desktop client for a local or remote runtime |
| Kubernetes Bundle | Helm/Kubernetes | Supported cluster deployment contract; operator-owned infrastructure |

Docker Compose is the supported first-release installation path for a complete
single-site runtime. It is also the reference implementation for the other
deployment targets. Air-gapped releases are offline copies of the Compose or
Kubernetes bundles with images and dependencies included.

## What Runs Where

The complete runtime is:

```text
Connectors -> validation -> Kafka -> Flink -> historian/lakehouse -> UI/AI
```

The Site Server or Kubernetes deployment runs the complete pipeline. The Edge
Collector runs connectors, validation, canonicalization, local buffering and
delivery to a site or central broker. Windows and macOS Operator packages are
clients; they do not need to run Kafka, Flink or TimescaleDB themselves.

## Resource Profiles

These are starting points for installation planning, not performance claims.
Actual capacity depends on event size, sampling rate, retention, partitions,
queries, dashboards, and model workloads.

### Edge Collector

- 2 CPU cores
- 4 GB RAM
- 20 GB SSD minimum, sized upward for store-and-forward duration
- No GPU

Suitable for a modest number of protocol connections and forwarding. Increase
disk capacity when the WAN may be unavailable for hours or days.

### Core Site Runtime Without AI Or Lakehouse

- 4 CPU cores minimum
- 8 GB RAM minimum for a small site
- 16 GB RAM recommended
- 100 GB SSD minimum, excluding long-term historian retention
- No GPU

This profile runs the API, Kafka, Flink, historian, fan-out, UI and monitoring
for evaluation or a modest site. It is the correct baseline for users who do
not enable local LLMs or a local lakehouse.

### Production Site Runtime

- 8 CPU cores recommended
- 16 to 32 GB RAM
- 250 GB or larger SSD, depending on retention and checkpoint policy
- Separate or faster storage for Kafka and TimescaleDB when possible
- No GPU required

This profile is for sustained traffic, larger retention, several sources,
concurrent dashboards and normal replay/analytics activity.

### AI Expansion

AI does not require a GPU inside the platform. Users may connect to a cloud or
company-hosted model endpoint. A GPU is only needed when the company chooses
local inference.

- Cloud or remote model: no additional GPU; reserve network bandwidth and AI
  gateway CPU/RAM for request batching.
- Small local model: usually 16 to 32 GB additional RAM, depending on model.
- Large local model: dedicated GPU/server sizing is model-specific and should
  not be included in the platform minimum.

The platform should report model-server requirements separately from platform
requirements.

### Lakehouse Expansion

MinIO, Iceberg, S3-compatible storage and large dataset reads increase storage
and network requirements but do not require a GPU. For serious training data,
use separate object storage and separate compute rather than enlarging the
operational site server indefinitely.

## Linux Site Server

The preferred complete single-site installation targets Ubuntu Server or Debian.
The installer registers services, creates persistent directories, runs database
migrations, provisions topics, starts Flink, and opens the commissioning UI.

Operators provide site identity, device endpoints, credentials/certificates,
retention, backups, optional external storage, and optional model endpoints.

## Windows Full Node

The complete stack should run inside a managed Linux appliance controlled by a
Windows installer. The Windows package should not require Docker Desktop in
production.

- Hyper-V is the production-oriented Windows option.
- WSL2 is an optional evaluation/development option.
- A Windows workstation can instead run the Operator package against a Linux
  Site Server.

Network OPC UA, MQTT, Modbus TCP and REST connections can pass through the
appliance. Serial Modbus is better handled through a serial-to-Ethernet gateway
or a native Edge Collector because physical serial passthrough into a VM is
deployment-specific.

## Windows And macOS Operator Packages

These packages install a desktop shell, CLI and diagnostics. They open the web
platform and can connect to a local or remote Site Server/Kubernetes runtime.
Closing the application must not stop ingestion on the runtime host.

## Kubernetes Bundle

The Helm package requires Kubernetes/K3s/RKE2, storage classes, ingress/TLS,
secret references, Flink Kubernetes Operator, and either bundled or external
Kafka and TimescaleDB. Companies own cluster capacity, identity, network policy,
backups, and GPU nodes.

## Operator Installation Flow

1. Verify the package checksum and signature.
2. Run the prerequisite check.
3. Select Edge, Site Server, Full Node, Operator, or Kubernetes mode.
4. Choose persistent configuration, data, logs and backup directories.
5. Configure local or external Kafka and historian services.
6. Configure optional MinIO/S3/Iceberg.
7. Configure optional LLM, embedding and model endpoints.
8. Register the runtime as an operating-system service or Kubernetes workload.
9. Run migrations and topic initialization.
10. Run `doctor`, preflight, health checks and a sample event test.
11. Add and test source connections in the UI.
12. Confirm data in Kafka, Flink, historian, Grafana and the platform dashboard.
13. Configure production backups, TLS, identity, retention and alert routing.
14. Run a backup/restore drill before production use.

## Operator-Owned Configuration

Users must provide:

- PLC, sensor and API endpoints
- OPC UA certificates and trust decisions
- MQTT credentials and topic permissions
- Modbus register maps and byte order
- REST field mappings and retry policy
- site, asset and tag semantics
- Kafka, database, MinIO or S3 endpoints when external
- retention and backup destinations
- TLS and AuthN/AuthZ integration
- model endpoints, model identifiers and GPU capacity when local inference is used

The platform owns the event contract, validation, normalization, Kafka topics,
processing, historian interface, replay, metadata contracts, AI gateway
contract, diagnostics and benchmark gates.

## Upgrade And Data Safety

Installers must keep configuration, historian data, Kafka data, checkpoints,
backups and logs outside replaceable application files. Upgrade flow:

1. Check compatibility and available disk space.
2. Back up configuration and databases.
3. Create a checksum and release manifest.
4. Stop or drain services according to the deployment mode.
5. Apply sequential migrations.
6. Start services and verify health.
7. Run a smoke event and release gate.
8. Roll back only with the documented backup and version compatibility procedure.

## Current Packaging State

The repository has packaging staging scripts, CLI entry points, runtime
supervision, release manifests, offline staging foundations, and installation
documentation. Windows/Linux/offline staging archives have been filtered and
validated locally: tests, `ObsidianVault`, development screenshots, Playwright
smoke files, and build targets are excluded while public guidance and demo
data remain available in the appropriate bundle. This is still release
staging, not a finished native installer. Final OS installer generation,
signing, upgrade automation, dependency assembly for clean machines, and
clean-machine acceptance tests remain packaging work.

The explicit staging targets are now:

```powershell
py -3.13 scripts/package-release.py --output-dir .datastream/release compose
py -3.13 scripts/package-release.py --output-dir .datastream/release kubernetes
```

The Compose target is the first release product. The Kubernetes target contains
the Helm chart, operator example, generated site values, runtime build inputs,
and public operator documentation. Neither target embeds customer secrets or
claims that Kafka, TimescaleDB, MinIO, GPUs, or the Flink Operator are supplied
by the platform.
