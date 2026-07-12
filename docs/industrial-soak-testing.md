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

The initial implementation phase adds the versioned scenario contract. The next
phase adds the live Docker runner and end-to-end report collection. Until that
runner is enabled, the existing `edge-soak.ps1` and `site-profile-soak.ps1`
remain the supported live smoke harnesses.
