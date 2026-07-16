# End-to-End Industrial Soak Testing

The repository contains two different performance test classes:

- in-process replay benchmarks measure transformation and serialization capacity
- industrial soak tests run protocol simulators through Kafka, processing, sinks,
  and observability for a sustained period

The default scenario is defined in `config/benchmarks/industrial-soak.yaml`.
It models OPC UA, MQTT, and Modbus sources, normal traffic, a burst, a source
reconnect, a Flink job restart, recovery, and a drain period. The scenario is
deliberately separate from customer data and does not claim to certify a real
PLC, sensor, network, or production disk.

Run a validation-only campaign with:

```text
datastreamctl benchmark industrial-soak --dry-run --smoke
```

Run the short live smoke campaign with:

```text
datastreamctl benchmark industrial-soak --smoke --report-dir reports/industrial-soak
```

Run the full staged campaign with:

```text
datastreamctl benchmark industrial-soak --report-dir reports/industrial-soak
```

The runner builds and starts the Compose stack, exposes simulator counters on host ports
`18091`-`18093`, samples edge/API/AI/Prometheus metrics, restarts the configured
source or Flink phases, and writes JSON and Markdown reports. The older
PowerShell soak scripts remain supported compatibility wrappers for simpler
edge-only tests.

## Real-Time Multisite Soak

For a wall-clock multi-site load test that keeps the platform running in real
time, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/multi-site-live-soak.ps1 `
  -Seconds 900 `
  -Sites 3 `
  -RatePerSecond 100 `
  -DeviceCount 50
```

This launches multiple site-qualified Kafka generators in parallel and feeds
the downstream runtime, fan-out consumers, historian, and AI gateway as a
live multi-site event stream. It is the closest local approximation to a
company with several sites sharing the same platform contract. It still does
not certify real PLC timing, fieldbus behavior, or customer network topology.
The soak harness treats processor metrics as optional in the Docker profile,
because the compose stack does not expose a standalone processor metrics
endpoint in every setup.

Each live generator now writes a delivery report under
`.datastream/logs/<soak-name>/<site>.report.json`. The report distinguishes
attempted, acknowledged, failed, queue-full, and effective-rate counts. The
configured rate is not treated as delivered traffic: acceptance reports must
use the acknowledged count and the downstream historian/Kafka accounting.
This prevents a slow local generator or producer queue from being mistaken for
pipeline capacity.

On Windows, generators stop through their duration control so Kafka delivery
callbacks and the final report are flushed before process exit. The PowerShell
wrappers wait for graceful exit and use process termination only as a timeout
fallback.

Fan-out workers now export bounded stage metrics for batch count, accepted and
rejected events, failed writes, and sink-write latency. The labels are limited
to service, topic, and status; site, asset, tag, and event IDs are deliberately
excluded to prevent Prometheus cardinality growth.

The threshold-policy cache optimization is documented in
`docs/benchmark-results-2026-07-13-threshold-cache.md`. It removed repeated
asset-hierarchy parsing from the keyed runtime path while preserving explicit
policy precedence. The current release extends that idea with an event-driven
policy snapshot and compacted Kafka distribution, so steady-state lookups do
not re-scan the historian or manifest on every event.

The Flink Compose deployment is replace-safe: after a job-image update, the
owned job is canceled before the replacement is submitted. A valid benchmark
must show exactly one active `iot-anomaly-processor` job.

The accounting helpers in `services/benchmarks/live_soak_accounting.py` are
pure and unit-tested. They calculate counter deltas, latency percentiles, and
the consecutive-zero drain condition used by the production soak runner.

Consumer lag is evaluated relative to the campaign's initial snapshot. A reused
development broker may already contain backlog; that backlog is reported but
does not fail the campaign unless the soak increases it. A clean release run
should start with zero lag or record the pre-existing backlog explicitly.

## Latest Local Smoke Result

On 2026-07-12, the rebuilt Docker smoke campaign passed all enabled gates. It
generated 6,815 simulator events, observed 9,030 edge-ingest events, held the
measured processing lag at 0 messages before and after the campaign, reached
6,255.1 MB peak aggregate container memory, and reported 38 historian writes at
the final snapshot. Reconnect, processor restart, recovery, and drain phases
completed.

The simulator and edge counters are different pipeline counters and should not
be compared as a delivery ratio. The current edge metrics do not expose a
DLQ-total or delivery-failure counter in this Compose profile, so the report
records those values as unavailable. A production acceptance gate should add
those counters before claiming lossless delivery.

The full default campaign on the same date also passed. It ran for 900 seconds,
generated 102,904 simulator events, observed 109,205 edge events, reached a
peak lag of 29 messages during the 470 events/sec burst, and returned to 0
messages after recovery and drain. Peak aggregate container memory was
6,463.1 MB and the historian write counter increased from 3 to 459. API and AI
health were healthy at completion. These are local Docker results, not a claim
of capacity for a production industrial site.

## Latest Single-Site vs Multisite Live Comparison

## Latest Flink Full-Stack Soak

On 2026-07-16, the corrected Flink-primary default scenario completed its
900-second wall-clock campaign after Docker Desktop/WSL recovery. It generated
114,649 simulator events and observed 118,350 edge events across the OPC UA,
MQTT, and Modbus simulator path. Warmup, sustained traffic, the 470 events/sec
burst, source reconnect, `flink-job` restart, recovery, and drain completed.
Flink, Prometheus, Kafka UI, Grafana, API, and AI health probes were healthy in
every phase. Final aggregate lag was zero and the report passed its configured
gates. Final probe latencies were Prometheus 13.47 ms, Kafka UI 11.36 ms, and
Grafana 13.65 ms.

The gateway memory fix was exercised: AI-gateway memory remained bounded at
approximately 184-246 MiB during the campaign and was 184.9 MiB afterward.
Aggregate container memory peaked at 5,159.5 MiB, so host sizing still matters.
The broker was reused rather than reset; it contained 12,761,368 messages of
pre-existing AI consumer lag at the initial snapshot and drained to zero. DLQ
and unaccounted-event counters were unavailable in this Compose profile, so
the run is evidence of runtime/recovery behavior, not a clean lossless capacity
or production sizing claim.

On 2026-07-13, the same local Docker stack was used for valid 15-minute
wall-clock soaks. Each generator ran for the full duration, flushed Kafka
delivery callbacks, and wrote an acknowledged-delivery report. The configured
rate was 100 events/sec per site:

- single-site: one run-qualified site
- multisite: three run-qualified sites

The Flink `iot-anomaly-processor` job was `RUNNING` with two tasks and the
replace-safe entrypoint verified that only one owned job was active. All
generators reported zero failed deliveries and zero producer queue saturation.

| Run | attempted | acknowledged | raw rows | processed rows | final fanout lag |
|---|---:|---:|---:|---:|---:|
| single-site | 89,996 | 89,996 | 89,996 | 89,996 | 0 |
| multisite | 269,992 | 269,992 | 269,992 | 269,992 | 0 |

The multisite run retained site identity and attributed the 269,992 rows to
the three sites as 89,997, 89,998, and 89,997 rows. Raw duplicate event IDs
were zero in the corrected attribution check. The multisite acknowledged rate
was effectively three times the single-site rate, within the generator timing
tolerance, rather than the 37% result recorded by the earlier harness.

The earlier `2,226` single-site and `3,049` multisite totals are retained only
as historical context. They were not valid capacity measurements because the
old Windows wrapper terminated generators before delivery reports were
flushed and therefore under-admitted the configured traffic.

## Current Deterministic Runtime Gate

The fresh 5,000-event local reference run used the production Flink runtime
contract with 500 warmup events and a batch size of 256:

| Metric | Result |
|---|---:|
| throughput | 9,026.12 events/sec |
| p50 latency | 0.0630 ms |
| p95 latency | 0.1622 ms |
| p99 latency | 0.3143 ms |
| invalid events | 0 |

Against the pre-cache production baseline of 132.53 events/sec, this is a
6,710% throughput improvement. This is an in-process/reference runtime gate,
not a claim that a Docker node will sustain the same rate over Kafka and
TimescaleDB. The measured bottleneck was repeated manifest policy parsing;
the mtime-aware cache removed that work from the keyed hot path.

AI enrichment is reported separately from the deterministic gate. Local AI
gateway runs may be `degraded` when the configured model endpoint is busy or
unavailable; that does not invalidate the Kafka-to-Flink-to-historian result.

## 2026-07-15 Full-Stack Validation Evidence

Three wall-clock campaigns were completed against the Docker Compose stack:

| Campaign | Duration | Input | Acknowledged | Final downstream lag | Flink | Prometheus/Kafka UI/Grafana |
|---|---:|---:|---:|---:|---|---|
| single-site normal | 900 s | 100 events/s | 89,990 | 0 | RUNNING, 2 tasks | healthy throughout |
| three-site normal | 900 s | 3 x 100 events/s | 269,986 | 0 | RUNNING, 2 tasks | healthy throughout |
| burst/recovery | 900 s staged | industrial-soak scenario | report passed | 0 after drain | RUNNING | healthy throughout |

The single-site producer reported zero failures and zero queue saturation. Each
of the three multisite producers also reported zero failures and zero queue
saturation. The staged burst/recovery runner recorded Flink state, Prometheus,
Kafka UI, Grafana, API health, fan-out lag, and UI probe latency at every phase.
Its peak aggregate container CPU was approximately 414.8% and peak memory was
approximately 8.43 GB. AI health degraded during the burst and recovered; the
deterministic Flink and historian path drained to zero lag.

Kafka UI and Grafana are not data-plane processors. They were tested as
operator-facing observability dependencies: HTTP reachability and response
latency were sampled during the soak. Final standalone probes returned HTTP
200 for Flink (`317.8 ms`), Prometheus (`28 ms`), Kafka UI (`77 ms`), Grafana
proxy (`373.6 ms`), API (`729.3 ms`), and AI gateway (`824.2 ms`).

The runner still cannot attribute all raw edge delivery and processor lag in
every Compose profile because those counters are not exposed by all services;
missing counters are reported as unavailable, not as zero. This is a
measurement gap, not evidence of lossless delivery.

## Backup Validation Finding

The backup harness was hardened to use Docker-hosted `psql`, include
TimescaleDB internal chunk schemas, and execute Timescale restore hooks. A
large local dump completed successfully (`~553 MB`, `88.9 s` backup and
`269.8 s` restore), and restored row data was present. However, a generic
`pg_restore` into a blank database did not reconstruct the source hypertable
metadata; `timescaledb_information.hypertables` remained empty. The backup
drill therefore remains a failed acceptance gate rather than a false pass.
Before production release, the restore path must initialize the target with a
compatible Timescale schema or use a Timescale-native backup/restore procedure
and verify row counts plus hypertable metadata. Do not interpret the current
local backup result as production-grade disaster-recovery evidence.
