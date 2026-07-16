# Measured SLO Evidence

The platform now distinguishes measured evidence from a health probe and from
unknown state. `GET /api/v1/observability/site` includes `slo_evaluation`, and
`GET /api/v1/observability/slo` returns the compact evaluation used by CLI and
release tooling.

## Measurements

When Prometheus has data, the evaluator measures maximum Kafka consumer lag,
AI request p95 latency, fan-out/historian write p95 latency, WebSocket
delivery p95 latency, and dead-letter rate. Targets are deployment-neutral
defaults and are visible in the response; operators should tune them for
their site profile rather than treating them as universal certification.

If Prometheus is unavailable or has no usable series, the result is
`unknown`, not `healthy` and not zero. The existing API health snapshot keeps
its compatibility fields, but API health is unknown unless
`DATASTREAM_API_HEALTH_URL` is explicitly configured.

## CLI

```powershell
datastreamctl observability slo --json
datastreamctl observability slo --require-slo-evidence
```

The strict form fails when the API is unreachable or any measurement is not a
measured passing value. The non-strict form reports unknown evidence without
blocking local development.

This is a release evidence gate, not an automatic paging system. Prometheus
alert rules and Grafana remain the continuous operator surfaces.

The fixed SLO query set is evaluated concurrently with bounded request
timeouts, so a missing Prometheus endpoint does not serialize five independent
network waits into every observability snapshot.
