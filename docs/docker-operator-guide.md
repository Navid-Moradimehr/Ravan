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
2. Replace every `CHANGE_ME` value, including both database users/passwords,
   MinIO credentials, and model credentials.
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

Kafka UI topic, consumer-group, and message views are enabled by default.
Broker JMX metrics are currently disabled because the Apache Kafka image's
startup agent conflicts with the broker's RMI port in the supported Compose
path. Do not treat the broker metrics page as an available release feature
until a separately validated JMX configuration is selected.

The host ports are configurable through `.env`; internal service ports and
service-to-service names do not change. The rehearsal file
`docker/rehearsal.env` assigns a complete alternate port set so an isolated
stack can run beside another Compose deployment.

## Isolated Local Rehearsal

To validate a fresh stack beside an existing local deployment, use the
rehearsal override. It assigns alternate host ports while preserving all
internal service addresses:

```powershell
docker compose -p ravan-rehearsal --env-file docker/rehearsal.env -f docker/docker-compose.yml --profile ui --profile edge up -d
```

For a full local pipeline rehearsal, use the industrial soak command from the
repository root. It enables the scenario's declared OPC UA, MQTT, and Modbus
protocols, records per-phase health and lag, restarts the configured component,
and writes JSON/Markdown evidence. This is a validation workflow, not a
production scheduler:

```powershell
$env:COMPOSE_PROJECT_NAME = "ravan-rehearsal"
Get-Content docker/rehearsal.env | ForEach-Object {
  if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
  }
}
py -3.13 -m services.cli.datastreamctl benchmark industrial-soak `
  --no-build --report-dir .datastream/industrial-soak --json
```

The acceptance gate requires healthy API and AI endpoints, a running Flink
job, reachable Prometheus/Kafka UI/Grafana endpoints, drained aggregate lag,
and no configured unaccounted-event allowance. Connector counters that are
not exposed by a selected profile are reported as unavailable rather than
silently interpreted as zero. Use the generated report together with the
deployment's own logs and retention policies; it is not a substitute for
real-site PLC certification or target-hardware sizing.
