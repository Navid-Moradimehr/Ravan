# Local Validation Evidence - 2026-07-16

## Passed without Docker

- Preflight contract validation.
- Local Kubernetes bundle rehearsal.
- Industrial soak dry-run.
- Three-site federation/outage simulation: 6,000 central events, zero
  duplicates, zero cross-site events, zero isolation errors, recovery complete.
- Fault campaign: 5,000 requested events, malformed/duplicate/out-of-order
  input, outage replay, zero unaccounted events, zero pending after recovery.
- Extended protocol, pipeline, model-data, lakehouse, governance, and Flink
  suites.

## Live runtime finding

Docker Compose recovered after a host restart and all core endpoints became
healthy. The first restarted 15-minute campaign was intentionally stopped
before acceptance when the AI gateway reached approximately 8.1 GB. The cause
was an unbounded scheduled-report evidence buffer, now bounded by
`max_evidence_events`. This campaign is not a passing or failing soak result;
rerun it after the fix.

## Corrected Flink Soak

The rerun completed the 900-second Flink-primary scenario with OPC UA, MQTT,
and Modbus simulators: 114,649 generated events, 118,350 edge events, source
reconnect, `flink-job` restart, recovery, and drain. Final lag was zero and
Flink, Prometheus, Kafka UI, Grafana, API, and AI probes stayed healthy. The
AI gateway remained approximately 184-246 MiB after the bounded staging fix.

The broker was reused and began with 12,761,368 pre-existing AI consumer lag,
which drained to zero. DLQ and unaccounted counters were unavailable, so this
is recovery evidence rather than a clean lossless throughput or production
sizing result.
