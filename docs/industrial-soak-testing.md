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
