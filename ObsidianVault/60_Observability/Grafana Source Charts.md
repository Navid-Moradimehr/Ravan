# Grafana Source Charts

Grafana is the advanced dashboard and alerting layer. It is not the source
registration surface.

## What it shows

- source state metrics by connection, protocol, and site
- last-success timestamps
- mapping match and miss counters
- per-source validated event throughput
- ingest throughput
- DLQ rate
- store-forward backlog
- AI gateway latency metrics

## Automatic source visibility

When a runtime source is saved and enabled in **Integrations**, the edge
runtime emits source-labelled Prometheus metrics. The provisioned **Connected
Sources** dashboard discovers the source using `site` and `connection_id`
variables. Kafka UI sees the source's published records automatically, and the
platform Observability page reads the same Prometheus-backed health signal.

## Operator flow

1. Register and enable the source in **Integrations**.
2. Confirm the source appears in **Pipeline** and **Observability**.
3. Open Grafana at `http://localhost:13000/`.
4. Open **Connected Sources** and use its site/source filters.
5. Add custom panels only for organization-specific views.

## Ownership boundary

- Grafana does not own source configuration.
- The platform does not create one Grafana dashboard object per source.
- Users own custom dashboards, alert rules, sharing, folders, and Grafana auth.

## Recommendation

Keep source onboarding in the platform UI and use Grafana for persistent shared
charts, alert rules, and cross-site comparisons. The default dashboard is
label-driven so its size remains stable as the registry grows.
