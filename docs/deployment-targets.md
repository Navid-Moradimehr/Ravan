# Ravan Deployment Targets

Ravan uses one event-driven runtime contract with several deployment shapes.
The deployment target changes where the services run, not the event model,
Kafka topics, historian contract, source configuration, or AI gateway API.

## First Release Targets

### Docker Compose Site Bundle

This is the supported first-release product for a complete single-site runtime.
It runs the dashboard, API, edge ingestion, Kafka, Flink, TimescaleDB,
Prometheus, Grafana, optional lakehouse services, and optional AI services on
one operator-managed host. Docker Desktop is suitable for evaluation on
Windows and macOS. Linux operators can use Docker Engine and Compose.

Build the staging bundle with:

```powershell
py -3.13 scripts/package-release.py --output-dir .datastream/release compose
```

The operator supplies host resources, persistent storage, device network access,
source credentials, retention, backups, and optional model or object-storage
endpoints. The package contains runtime build inputs and public documentation;
it does not contain secrets, tests, or the Obsidian vault.

### Kubernetes and Helm Bundle

This target is for organizations that already operate Kubernetes, K3s, or RKE2.
It provides the Ravan Helm chart, generated site configuration, Flink
deployment contract, and the Flink Kubernetes Operator runbook. Kafka,
TimescaleDB, object storage, ingress, storage classes, identity, and cluster
policies remain operator-owned unless the operator deliberately provisions
compatible dependencies.

Build the staging bundle with:

```powershell
py -3.13 scripts/package-release.py --output-dir .datastream/release kubernetes
```

Install the Apache Flink Kubernetes Operator separately, publish or load the
Flink image into the cluster's registry, then render and validate the chart
before applying it. The local kind rehearsal validates manifests and operator
reconciliation; it is not a production multi-node certification.

## Later Targets

Linux systemd, Windows full-node, Windows Operator, and macOS Operator packages
are separate later products. They require bundled runtime dependency strategy,
service lifecycle handling, upgrade and rollback behavior, code signing, clean
machine acceptance, and OS-specific network/device testing. They must not be
represented as finished installers merely because their generated configuration
files already exist.

## Target Selection

Use Compose when one site needs a complete self-hosted runtime or when the
operator wants the lowest deployment complexity. Use Kubernetes when the
company already has cluster operations, shared storage, site federation,
failure-domain requirements, or a managed Flink Operator process. Use an Edge
Collector shape only when connectors must run near equipment and forward to a
separate Site Server or central Kafka deployment; this remains an architecture
profile, not a separate installer in the first release.

## Common Contract

All targets preserve:

- canonical industrial events and versioned Kafka topics;
- deterministic validation, normalization, Flink processing, replay, and historian sinks;
- metadata, semantic, lineage, and AI gateway contracts;
- operator-owned secrets, AuthN/AuthZ, TLS, retention, backups, and external integrations.

The package target is therefore a deployment boundary, not a second platform.
