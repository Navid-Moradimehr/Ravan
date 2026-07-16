# Measured SLO Evidence

## Status

Implemented on 2026-07-16. Observability no longer presents hardcoded API
health or boolean AI latency as production evidence.

## Measurements

The platform evaluates Prometheus-backed consumer lag, AI request p95,
fan-out write p95, WebSocket delivery p95, and DLQ rate. Missing Prometheus
series are `unknown`, not zero. Probe results include availability and probe
latency, while model latency comes from the AI histogram when available.

## Interfaces

- `GET /api/v1/observability/site`
- `GET /api/v1/observability/slo`
- `datastreamctl observability slo --json`
- `datastreamctl observability slo --require-slo-evidence`

Prometheus/Grafana remain the continuous monitoring layer. The evaluator is a
bounded release/readiness evidence layer.

[[Agent Governance Boundary]]
[[Production Readiness Validation 2026-07-15]]
