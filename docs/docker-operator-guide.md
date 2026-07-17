# Ravan Docker Operator Guide

Ravan's first-release deployment path is Docker Compose. It is self-hosted:
the company owns networking, TLS, identity, credentials, retention, and every
external endpoint. Ravan owns the service contracts, default topology, health
checks, and operator workflows.

## No Host Python Requirement

The Docker path does not require an operator to install Python. Use the wrappers
from the repository root:

```powershell
.\scripts\ravan.ps1 up -d
.\scripts\ravanctl.ps1 doctor
.\scripts\ravanctl.ps1 preflight --strict
.\scripts\ravanctl.ps1 status
```

On Linux and macOS, use `./scripts/ravan.sh` and `./scripts/ravanctl.sh`.
`ravanctl` executes inside the API container and uses the same pinned runtime
dependencies as the service. Python remains an optional developer dependency
for source checkout, test, benchmark, and custom-extension workflows.

## Profiles And Runtime Ownership

`ravan` starts the UI and `edge` profiles. It does not start protocol simulators.
Production source endpoints are configured through Source Connections and
operator-owned environment/configuration values.

When no Source Connection is enabled, edge ingest remains healthy and idle.
The production Compose profile never attempts bundled simulator endpoints.

```text
Production: UI + Edge + Kafka + Flink + historian/fan-out services
Demo:       Production services + explicit `demo` profile simulators
Fallback:   explicit `python-fallback` profile only; never run it with Flink
```

Flink is the default production processor. The Python fallback exists for
local development and diagnostic comparison. Do not start `processor` while
`flink-job` is consuming the same topic: they use separate consumer groups and
would both process the records.

Start a demo only when intentionally validating the bundled simulators:

```powershell
docker compose -f docker/docker-compose.yml --profile ui --profile edge --profile demo up -d
```

## Required Operator Configuration

1. Copy `.env.production.example` to `.env`.
2. Replace demo database, MinIO, Grafana, and model credentials.
3. Configure real broker and protocol endpoints through Source Connections or
   deployment configuration. The production `edge` profile has no dependency
   on simulator containers.
4. Configure TLS, firewall rules, SSO/RBAC, and secret delivery according to
   the company network policy.
5. Run `ravanctl preflight --strict`, then a backup drill, before production
   traffic is enabled.

## Browser And API Routing

The UI proxies AI telemetry through its own `/api/telemetry` route, so browser
clients do not need direct access to the AI gateway port. WebSocket telemetry
derives its host from the browser URL and uses port `8020`; expose or reverse
proxy that endpoint when operators use a remote browser. Set
`DATASTREAM_CORS_ALLOW_ORIGINS` to the exact UI origins served by the company.
The default only permits local Ravan UI on port `3006`.

## Kubernetes Preview

The Helm chart is a self-hosted deployment contract, not a hosted control
plane. It defaults to the Flink production runtime and versioned Ravan image
names. Operators must set their own image registry, secrets, Kafka,
TimescaleDB, object storage, ingress, TLS, and identity integration before
applying it to a real cluster.

## Operational Notes

`kafka-init` and `timescaledb-migrate` are one-shot initialization services.
They normally exit with status zero after completing their work. A stopped
container is expected; inspect its exit code and logs only when it is nonzero.

The Kafka JMX endpoint is enabled for Kafka UI broker metrics. It is intended
for the local Compose network; expose it beyond the host only through the
operator's secured observability design.
