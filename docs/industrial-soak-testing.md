# End-to-End Industrial Soak Testing

The repository contains two different performance test classes:

- in-process replay benchmarks measure transformation and serialization capacity
- industrial soak tests run protocol simulators through Kafka, processing, sinks,
  and observability for a sustained period

The default scenario is defined in `config/benchmarks/industrial-soak.yaml`.
It models OPC UA, MQTT, and Modbus sources, normal traffic, a burst, a source
reconnect, a processor restart, recovery, and a drain period. The scenario is
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
source or processor phases, and writes JSON and Markdown reports. The older
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

On 2026-07-13, the same local machine was used for two 15-minute wall-clock
soaks with the same downstream stack and the same configured per-site generator
rate:

- single-site: one generator at 100 events/sec
- multisite: three generators at 100 events/sec each

Both runs kept fanout lag at 0 during the final snapshots and the Flink
`iot-anomaly-processor` job stayed `RUNNING` with two tasks.

Final historian-write counters from the live runs:

| Run | industrial_events | processed_events | ai_enriched |
|---|---:|---:|---:|
| single-site | 2,226 | 2,210 | 1,754 |
| multisite | 3,049 | 3,036 | 2,171 |

Interpretation:

- multisite produced about 37% more historian writes than single-site on the
  same node, not 3x more
- the downstream path stayed healthy, but the node did not scale linearly with
  the added sites
- the single-node setup is acceptable for a pilot or a small site, but a
  sustained multi-site rollout should plan for additional nodes earlier than a
  naive throughput model would suggest

This is the most important local signal from the soak: the platform is
operationally stable, but the single-node ceiling is visible once multiple
equal-rate sites are added.
