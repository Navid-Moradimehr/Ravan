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

The runner starts the Compose stack, exposes simulator counters on host ports
`18091`-`18093`, samples edge/API/AI/Prometheus metrics, restarts the configured
source or processor phases, and writes JSON and Markdown reports. The older
PowerShell soak scripts remain supported compatibility wrappers for simpler
edge-only tests.
