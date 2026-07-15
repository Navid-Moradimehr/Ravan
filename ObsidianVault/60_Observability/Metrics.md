# Metrics

## Core Metrics

- Ingest messages per second
- Consumer lag by topic and group

## Industrial Soak Campaigns

The versioned scenario contract at `config/benchmarks/industrial-soak.yaml`
defines the future end-to-end soak workload. It is intended to account for
generated, raw, normalized, processed, persisted, DLQ, and recovered events,
alongside Kafka lag, latency, CPU, memory, disk, reconnect, and dashboard
health. In-process replay numbers must not be presented as equivalent to this
live protocol path.
- Processing latency
- LLM request latency
- LLM batch size
- LLM batch severity totals
- CDC event count and lag
- Service health status
- Edge ingest Kafka delivery failures (`edge_ingest_delivery_failures_total`, by topic)
- Edge ingest overflow / DLQ routing (`edge_ingest_overflow_total`, by reason: `message_too_large`, `mqtt_queue_full`)

## Dashboard Surface

- Throughput line chart by protocol
- AI latency and batch size area chart
- Protocol mix bar chart
- Severity mix bar chart
- Grafana health card with local `/login` link

## Failure Handling

- If Prometheus is unavailable, the dashboard uses a built-in fallback snapshot.
- If Grafana is unavailable, the dashboard shows an offline badge and disables the local Grafana action.

## Alert Rules (added 2026-07-06)

> Competitive inspiration 5 (pillar 07 - lag/health monitoring).

The platform emitted metrics but had no alert rules, so backlog and failures
grew silently. `docker/prometheus/alert_rules.yml` adds 9 alerts in 4 groups,
all referencing metrics the services actually emit:

**Consumer lag** (`datastream_broker_consumer_lag_messages`)
- `ConsumerLagHigh` (warning): sum by service/topic > 1000 for 2m.
- `ConsumerLagCritical` (critical): sum by service/topic > 10000 for 5m.

**Delivery health**
- `DLQRateHigh` (warning): `rate(edge_ingest_dlq_total[5m])` > 1/sec for 5m.
- `EdgeOverflowSustained` (warning): `edge_ingest_overflow_total` rate > 0 for 5m (bounded queue saturated).
- `KafkaDeliveryFailures` (critical): `edge_ingest_delivery_failures_total` rate > 0 for 2m.
- `AdapterReconnectStorm` (warning): `edge_ingest_reconnects_total` rate > 0.5/sec for 5m.

**Historian**
- `HistorianWriteFailures` (critical): `historian_write_total{status="failed"}` rate > 0 for 2m (events not persisting; fan-out may stall).
- `HistorianQuerySlow` (warning): p95 `datastream_historian_query_latency_seconds` > 1s for 5m.

**Realtime**
- `WebSocketDeliveryLagHigh` (warning): p95 `datastream_websocket_delivery_lag_seconds` > 5s for 5m.

### Wiring

- `prometheus.yml` registers the rules via `rule_files`.
- `docker-compose.yml` mounts `./prometheus/alert_rules.yml` read-only into the prometheus container.
- Thresholds are conservative open-source baselines; tune `for` windows and severity to SLOs.
- Prometheus alerts route to Alertmanager (if an operator adds one). The API-level `AlertManager` + `EscalationEngine` (Apprise/webhook) is a complementary application-layer alert system.

### Tests

`tests/test_prometheus_alert_rules.py` (7 cases): valid YAML, required fields per alert, every expr references a known metric, key alerts present, config + compose wiring correct.

## Related

- `comparission.md` pillar 07
- [[20_Architecture/Sink Architecture]] (historian write failures stall fan-out)

## Industrial Soak Campaigns

Run `datastreamctl benchmark industrial-soak --dry-run --smoke` to validate a
scenario without Docker. Use `--smoke` for the 30-second Compose campaign and
the default command for the staged 15-minute campaign. Reports are written as
JSON and Markdown and combine simulator generation, edge acceptance, DLQ,
consumer lag, resource, API, and AI signals.

Latest local Docker smoke (2026-07-12): passed. The rebuilt campaign generated
6,815 simulator events, observed 9,030 edge events, measured consumer lag at
0 -> 0, peaked at 6,255.1 MB aggregate container memory, and reported 38
historian writes at the final snapshot. DLQ and delivery-failure totals remain
unavailable in the current edge metric surface; they are not treated as zero.

Full default campaign (900 seconds, 2026-07-12): passed. It generated
102,904 simulator events and observed 109,205 edge events. Peak measured lag
was 29 messages during the burst and returned to 0 after recovery/drain.
Peak aggregate container memory was 6,463.1 MB; historian writes increased
from 3 to 459. This is a local Docker benchmark, not a production capacity
claim. DLQ/delivery-failure counters remain a release-hardening gap.

## 2026-07-15 Validation Update

The current local Docker evidence includes three 15-minute campaigns: one
single-site normal-load run at 100 events/sec, one three-site run at 100
events/sec per site, and one staged burst/recovery run. Acknowledged delivery
was 89,990 for the single site and 269,986 across three sites; final downstream
lag was zero; Flink was RUNNING with two tasks. Prometheus, Kafka UI, and
Grafana were sampled throughout the staged campaign and remained reachable.

The first live run also found and fixed a missing `psycopg2-binary` dependency
in the Flink runtime image. The backup drill found a separate limitation:
generic restore brings back rows but not Timescale hypertable metadata in a
blank target. Backup acceptance remains open until the restore procedure
reconstructs and verifies hypertables. Missing edge-DLQ and processor metrics
remain measurement gaps, not zero values.
# Local Resilience Campaign

The repository now has a deterministic broker-free resilience campaign at
`datastreamctl benchmark resilience`. It exercises the canonical validator and
edge disk spool with malformed events, duplicate identities, out-of-order
timestamps, a simulated outage, and replay recovery. It reports unaccounted
events, queued/replayed records, pending spool records, and peak memory.

This complements, rather than replaces, the Docker-backed industrial soak
campaign. The local campaign validates accounting and recovery contracts; the
Docker campaign validates service, broker, historian, and container behavior.
