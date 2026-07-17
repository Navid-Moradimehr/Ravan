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

The package contains two Compose definitions. `docker/docker-compose.yml` is
the source-build development/evaluation definition. The generated
`docker/docker-compose.release.yml` is the Linux Site Server definition: it
expects Ravan images in a registry and does not depend on a source checkout or
Flink processor bind mounts. Set the image registry and release tag before
starting it:

```bash
export RAVAN_IMAGE_REGISTRY=ghcr.io/navid-moradimehr
export RAVAN_VERSION=1.0.0-beta.1
export RAVAN_COMPOSE_FILE=docker/docker-compose.release.yml
./scripts/ravan.sh up -d
```

The official image publication workflow is a separate release concern. A
local package is not usable with the release Compose file until the selected
Ravan images have been published to, or mirrored into, the operator's
registry. Docker Engine is the intended Linux runtime; Docker Desktop is an
evaluation convenience on Windows and macOS.

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

## Advanced Host Runtime Target

The generated Linux systemd and Windows service layouts are an advanced host
runtime target, not a replacement for the complete Compose site bundle. They
run the Ravan application processes under an OS service manager while Kafka,
TimescaleDB, Flink, and other infrastructure remain operator-supplied. The
service manager now starts the foreground `datastreamd supervise` command,
which owns child processes, performs bounded restarts, and shuts them
down as one unit. These layouts still require clean-machine, dependency, and
device network acceptance before being advertised as polished installers.

Windows and macOS operator shells remain separate later products. They should
control a Site Server rather than silently pretending that a workstation can
replace the complete industrial runtime.

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
