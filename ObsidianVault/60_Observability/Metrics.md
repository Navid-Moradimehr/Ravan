# Metrics

## Core Metrics

- Ingest messages per second
- Consumer lag by topic and group
- Processing latency
- LLM request latency
- LLM batch size
- LLM batch severity totals
- CDC event count and lag
- Service health status

## Dashboard Surface

- Throughput line chart by protocol
- AI latency and batch size area chart
- Protocol mix bar chart
- Severity mix bar chart
- Grafana health card with local `/login` link

## Failure Handling

- If Prometheus is unavailable, the dashboard uses a built-in fallback snapshot.
- If Grafana is unavailable, the dashboard shows an offline badge and disables the local Grafana action.
