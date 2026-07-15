# Production Readiness Validation - 2026-07-15

## Evidence

- Full Python suite: `627 passed`, 4 existing warnings.
- Extended protocol matrix: `46 passed`, 2 deprecation warnings.
- Compose configuration: valid.
- Flink job: `iot-anomaly-processor`, `RUNNING`, 2 tasks, 0 failed.
- Single-site soak: 900 seconds, 89,990 acknowledged, 0 failures, 0 queue-full.
- Three-site soak: 900 seconds, 269,986 acknowledged, 0 failures, 0 queue-full.
- Burst/recovery soak: 900 seconds, passed staged gates, final lag 0.
- Final probes: Flink, Prometheus, Kafka UI, Grafana, API, and AI returned HTTP 200.

Kafka UI and Grafana were monitored as operator observability dependencies.
They do not process or persist the industrial stream themselves.

## Fixes Found During Validation

1. Added `psycopg2-binary` to the Flink runtime image after a real PyFlink
   worker import failure.
2. Isolated implicit resilience benchmark spools so concurrent campaigns cannot
   corrupt accounting.
3. Added Flink and observability endpoint probes to the soak runner.
4. Added Docker-hosted PostgreSQL snapshot fallback for Windows hosts.

## Open Gate

The Timescale backup drill now passes end-to-end on a disposable clean target.
The backup path switched to a full-database logical dump, the drill resets the
restore target before running, and the restore verification now checks both
row identity and `timescaledb_information.hypertables`.

The remaining release gates are the non-local items: real-site sizing,
real PLC/sensor validation, and repeatability on target hardware.

Raw edge delivery and standalone processor lag are unavailable in some Compose
profiles because the corresponding counters are not exposed. The validation
reports these as unavailable, not as zero.
