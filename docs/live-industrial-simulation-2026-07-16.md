# Live Industrial Simulation Results: 2026-07-16

## Scope

Two wall-clock campaigns were run against the Docker deployment on the same
single host. Both used `services.ingestion.mock_generator` publishing directly
to Kafka topic `industrial.normalized`; this validates the Kafka, Flink,
processing, historian, and fan-out path, but does not replace native OPC UA,
MQTT, or Modbus connector testing.

The production Flink job was left enabled. The Python processor fallback was
not started.

## Results

| Campaign | Duration | Producers | Target rate | Attempted | Acknowledged | Failed | Queue full | Final fan-out lag |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Single site `single-345a3007e700-site-01` | 900 s | 1 | 100/s | 89,999 | 89,999 | 0 | 0 | 0 |
| Three sites `multi-cf3338b1058e-site-{1,2,3}` | 900 s | 3 | 100/s/site | 270,000 | 270,000 | 0 | 0 | 0 |

The single-site effective rate was `99.999 events/s`. Each multisite producer
also achieved `99.999 events/s`.

TimescaleDB accounting for the multisite window was exact:

- `industrial_events`: 90,000 rows per site, 270,000 total
- `processed_events`: 90,000 rows per site, 270,000 total
- dead-letter rows: 0

The Flink job stayed `RUNNING` with two active tasks. API and AI gateway health
were `ok`, and normalized, processed, and AI fan-out services all reported
zero final lag. Prometheus readiness, Grafana health, and Kafka UI returned
HTTP 200 after the campaign.

## AI Reporting Qualification

The persisted default policy at test time was:

- scheduled reporting: enabled
- scheduled interval: 3,600 seconds
- anomaly reporting: disabled
- anomaly duration: 20 seconds

Because both campaigns were 900 seconds, they correctly did not trigger a
scheduled AI report. `ai_enriched` therefore did not gain rows from these
campaigns. The `ai-gateway` consumer showed approximately 420,470 messages of
lag because it retains offsets until the bounded evidence batch is successfully
reported. This is policy-controlled evidence retention, not proof of historian
loss, but it means Kafka lag for this consumer must not be interpreted as
ordinary processing lag. A separate AI soak should use a temporary 600-second
policy or a sustained-anomaly fixture, then restore the operator policy.

## Acceptance

The core streaming and historian path passed this local single-node test with
zero producer failures, zero queue-full events, zero DLQ rows, exact source to
historian accounting, and zero final sink lag. This is strong local evidence
for the Kafka/Flink/historian path at 100 events/s on one site and 300 events/s
across three sites. It is not certification for native industrial protocols,
customer networks, or multi-node production capacity.

Commands used:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/single-site-live-soak.ps1 -Seconds 900 -RatePerSecond 100 -DeviceCount 50 -Topic industrial.normalized
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/multi-site-live-soak.ps1 -Seconds 900 -Sites 3 -RatePerSecond 100 -DeviceCount 50 -Topic industrial.normalized
```
