# Industrial Edge Pipeline

The project now has a hardware-free industrial edge tier.

## Components

- `edge-ingest`: bridges OPC UA, MQTT, and Modbus TCP payloads into Redpanda.
- `opcua-sim`: deterministic OPC UA tag simulator for `Pump-01`.
- `mqtt-broker` and `mqtt-sim`: broker plus telemetry publisher.
- `modbus-sim`: Modbus TCP holding-register simulator for `Pump-03`.

## Topics

- `industrial.raw`: raw protocol-shaped payloads.
- `industrial.normalized`: validated canonical envelopes.
- `industrial.dlq`: malformed or invalid payloads.
- `iot.raw`: compatibility stream for the existing processor.
- `iot.processed`: downstream enriched stream produced by the Python fallback processor or the distributed Flink job.

## Operating Assumption

Real plants normally use configured drivers/gateways instead of automatic PLC/sensor discovery. This project validates that downstream pattern locally with mock protocols.

The processing contract is intentionally shared so the host-run Python processor and the keyed-state Flink job emit the same enriched payload shape.
