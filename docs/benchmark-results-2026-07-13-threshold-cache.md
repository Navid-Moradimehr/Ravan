# Benchmark Results: Threshold Policy Cache

## Scope

The keyed enrichment benchmark was repeated with the same mixed industrial
CSV, 5,000 measured events, 500 warmup events, batch size 256, window size 25,
and local Python 3.13 environment.

## Result

| Metric | Before | After | Change |
|---|---:|---:|---:|
| End-to-end production-pipeline rate | 132.53 events/sec | 10,690.41 events/sec | +7,964% |
| Keyed enrichment rate | 146.84 events/sec | 25,880.85 events/sec | +17,524% |
| End-to-end p50 latency | 5.9312 ms | 0.0645 ms | -98.9% |
| End-to-end p95 latency | 11.9697 ms | 0.1267 ms | -98.9% |

The comparable Flink-runtime slice increased from 125.43 to 9,050.56
events/sec (+7,118%) in the same local reference benchmark. This is a
deterministic reference slice, not proof of networked Flink throughput.

## Cause

When no explicit database policy existed, threshold resolution loaded and
walked the complete asset hierarchy for every event. The implementation now
caches the derived manifest-policy map and invalidates it when the asset file's
modification time changes. The current release keeps the same explicit policy
precedence but also publishes policy edits through a compacted Kafka topic so
steady-state runtime consumers can stay on a lookup-only snapshot instead of
re-querying the historian on every sample.

## Validation

- Threshold and scoring tests: passed.
- Focused soak/accounting tests: passed.
- Python compilation: passed.
- Live 20-second single-site smoke after the measurement changes: 2,000
  attempted, 2,000 acknowledged, zero producer failures, zero queue-full
  events, zero final deterministic lag.

## Fresh runtime gate

A fresh 5,000-event run with 500 warmup events and batch size 256 measured the
production Flink runtime contract at 9,026.12 events/sec, p50 0.0630 ms, p95
0.1622 ms, and p99 0.3143 ms. This is within normal local-run variance of the
earlier 9,050.56 events/sec reference result. The result is intentionally kept
separate from the end-to-end Docker soak because it measures the deterministic
runtime slice rather than broker, network, database, and AI gateway capacity.
