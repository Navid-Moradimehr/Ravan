# Live Soak Measurement Contract

The live single-site and multisite tests measure admitted traffic, not merely
the requested generator rate. Each mock generator uses Kafka delivery
callbacks and writes a report to `.datastream/logs` with attempted,
acknowledged, failed, queue-full, and effective-rate values.

The report is valid only when the downstream accounting is collected as well:
Kafka offsets, consumer lag, historian row deltas, processed rows, AI output
rows, DLQ deltas, duplicates, latency percentiles, and the drain duration.
The `live_soak_accounting` module contains the deterministic rules and is
covered by unit tests.

## Current phase

- Measurement foundation implemented and committed.
- Generator scheduling no longer accumulates per-event sleep drift.
- Delivery failures and producer queue saturation are visible.
- Windows runners wait for graceful generator completion before fallback
  termination.
- Fanout stage metrics are bounded and available in Prometheus.
- A valid 15-minute single-site and three-site comparison has passed with
  acknowledged delivery, historian attribution, zero duplicates, and zero
  final fanout lag.

Fan-out services now expose bounded Prometheus counters and histograms for
batch outcomes, accepted/rejected events, failed writes, and sink latency.
Metrics are labelled only by service, topic, and status.

The Windows runners use a generator duration rather than immediately killing
the child process. This is required for delivery callbacks and final JSON
reports to be flushed reliably.

## Measured optimization

The threshold-policy manifest lookup is now cached by asset-file modification
time. The 5,000-event reference pipeline increased from 132.53 to 10,690.41
events/sec, while p95 latency fell from 11.9697 ms to 0.1267 ms. See
`docs/benchmark-results-2026-07-13-threshold-cache.md` for the exact method and
limits of this result.

The Docker Flink lifecycle now cancels previously active jobs with the owned
job name before submitting a replacement. The runtime check must show one
active job and no duplicate consumers.

## 2026-07-13 acceptance results

| Run | attempted | acknowledged | raw rows | processed rows | final lag |
|---|---:|---:|---:|---:|---:|
| single-site, 15 minutes | 89,996 | 89,996 | 89,996 | 89,996 | 0 |
| three-site, 15 minutes | 269,992 | 269,992 | 269,992 | 269,992 | 0 |

The prior low totals were invalid because the old harness stopped the producer
before delivery callbacks and final reports were flushed. The corrected
measurement uses acknowledged Kafka deliveries and downstream row deltas.

The fresh deterministic runtime gate measured 9,026.12 events/sec, p50
0.0630 ms, p95 0.1622 ms, and p99 0.3143 ms. Relative to the pre-cache
132.53 events/sec baseline, the measured throughput improvement is 6,710%.
This is a local reference result, not an end-to-end Docker capacity promise.

## Capacity boundary: 2026-07-13

Short capacity probes on the same Compose node produced these boundaries:

- 5 sites x 500 events/sec: approximately 2,499 admitted events/sec, zero
  final normalized-fanout lag.
- 10 sites x 1,000 events/sec: approximately 9,967 admitted events/sec and
  29,043 messages of recoverable final lag; the lag drained in about one minute.
- 20 sites x 1,000 events/sec: approximately 15,969 admitted events/sec,
  133,231 messages of final normalized-fanout lag, and failure of the zero-lag
  gate.

The high-rate soaks use `source_protocol=mock` and publish directly to Kafka.
They validate the common downstream path, not protocol-specific wire behavior.
MQTT, OPC UA, and Modbus TCP have separate Docker simulators and connector
smoke coverage. A small connector contract matrix is still required; separate
15-minute capacity runs for every protocol are not necessary.

## Interpretation rule

Never compare historian totals to the configured rate alone. First verify the
generator acknowledged count, then account for historian rows, DLQ rows, and
remaining Kafka lag. Unexplained acknowledged events fail the run.
