# Latest Benchmark Results

This document contains the latest successful local validation results for the
Ravan release package. It reports Ravan measurements only. It is not a vendor
comparison and does not represent certification for a real industrial site.

## Deterministic Runtime Reference

Measured on 2026-07-13 with the mixed industrial event dataset, 5,000 measured
events, 500 warmup events, batch size 256, and window size 25:

| Metric | Result |
|---|---:|
| Production Flink runtime rate | 9,026.12 events/sec |
| p50 latency | 0.0630 ms |
| p95 latency | 0.1622 ms |
| p99 latency | 0.3143 ms |

This is a deterministic runtime reference slice. It does not measure the
combined limits of Kafka, the network, TimescaleDB, object storage, or an AI
provider.

## Local Resilience And Multi-Site Validation

The latest successful local resilience campaign processed 10,000 events with
malformed, duplicate, out-of-order, and outage cases:

- Accepted: `9,897`
- Rejected malformed: `103`
- Replayed after outage: `1,961`
- Unaccounted events: `0`
- Pending spool after recovery: `0`

These results validate deterministic accounting for the supplied event
fixtures. They do not certify real PLCs, industrial networks, Kafka federation,
or production Kubernetes capacity.

## Interpretation

Users should treat these numbers as repeatable local reference measurements.
Actual capacity depends on event size, connector protocol, partition count,
Flink parallelism, historian retention, storage latency, dashboard reads, AI
usage, and host resources. Each deployment should repeat the included smoke,
resilience, protocol, and soak tests with its own configuration.
