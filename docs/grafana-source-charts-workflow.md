# Grafana Source Charts Workflow

Grafana is the platform's advanced visualization and alerting workspace. It is
the right place for durable charts, shared dashboards, alert rules, and
cross-site comparisons. It does not own source configuration. Source onboarding
still happens in **Integrations**.

## What Grafana can show today

The platform already exposes source-facing metrics through Prometheus:

- `edge_source_state{connection_id,protocol,site}`
- `edge_source_last_success_epoch{connection_id,protocol,site}`
- `edge_source_mapping_seen_total{connection_id,protocol,site}`
- `edge_source_mapping_match_total{connection_id,protocol,site}`
- `edge_source_mapping_miss_total{connection_id,protocol,site}`
- `edge_ingest_source_events_total{connection_id,protocol,site}`
- `edge_ingest_events_total{protocol}`
- `edge_ingest_dlq_total{protocol}`
- `edge_ingest_reconnects_total{protocol}`
- `edge_store_forward_pending`
- `ai_gateway_llm_request_seconds_bucket`

Grafana can chart these metrics once the panels are configured.

## What is automatic

After a runtime source is saved and enabled in **Integrations**, the edge
runtime publishes its source-labelled metrics to Prometheus. The default
Grafana provisioning loads the **Connected Sources** dashboard, which discovers
sites and connection IDs through dashboard variables. Users do not need to
enter PromQL metric names or create one panel per source.

Kafka UI is also automatic for runtime sources: once a connector publishes,
the configured Kafka topics and records are visible in the broker console.
Prometheus exposes the raw series, and the platform Observability page reads a
summary of those series.

## What the user should do

1. Open **Integrations**, save the source connection, and enable it.
2. Verify the source becomes visible in **Pipeline** and **Observability**.
3. Open **Grafana** from the Command Center or use `http://localhost:13000/`.
4. Open the provisioned **Connected Sources** dashboard.
5. Select a site or source from the dashboard filters when narrowing the view.
6. Create additional panels only when the company needs a custom calculation,
   retention view, or cross-system dashboard.

## Recommended panels for connected sources

- Source state by connection ID
- Last success time by source
- Mapping misses by source
- Mapping match ratio by source
- Ingest throughput by protocol
- DLQ rate by protocol
- Store-forward backlog

## What users may configure

The platform supplies the default source dashboard and its discovery filters.
Users still own custom Grafana dashboards, alert thresholds, folders, sharing,
and any organization-specific PromQL. The platform does not write Grafana
credentials or secrets into the source registry.

For the current Docker Compose deployment, the default Grafana stack already has
the Prometheus datasource provisioned and a starter dashboard in
`docker/grafana/dashboards/local-stream-engine.json`.

## When to use Grafana versus platform charts

- Use the platform UI when you want source onboarding, pipeline state, replay,
  historian SQL, or operator-managed workflows.
- Use Grafana when you want persistent shared dashboards, custom Prometheus
  queries, or cross-site health views.

## Dashboard design boundary

The default dashboard is label-driven rather than one-dashboard-per-source.
That avoids creating unbounded Grafana objects as sites and sensors are added,
while still making every enabled runtime source visible automatically. The
source registry remains the configuration authority; Grafana is only the
observability projection.
