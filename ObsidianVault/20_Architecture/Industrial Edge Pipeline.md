# Industrial Edge Pipeline

The project now has a hardware-free industrial edge tier.

## Components

- `edge-ingest`: bridges OPC UA, MQTT, and Modbus TCP payloads into Kafka.
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

## MQTT Delivery Options (added 2026-07-06)

> Competitive inspiration 2 (pillar 05 - MQTT 5.0 maturity).

The MQTT adapter subscriber is now configurable for production-grade delivery
semantics, via `services/edge_ingest/settings.py`:

- `MQTT_QOS` (default `1`) - subscription QoS. QoS 0 = at-most-once (fire and
  forget); QoS 1 = at-least-once (the existing behavior); QoS 2 = exactly-once
  (broker-level handshake). The adapter's bounded decoupling queue + DLQ path
  already handles at-least-once; raising QoS to 2 tightens the broker edge.
- `MQTT_RETAINED` (default `true`) - declares retained-message availability so
  operators know whether the broker keeps the last known good value per topic
  (useful for late subscribers reading the current state on startup).
- `MQTT_WILL_TOPIC` / `MQTT_WILL_PAYLOAD` / `MQTT_WILL_QOS` / `MQTT_WILL_RETAIN`
  - Last Will and Testament. When set, the broker publishes the will if the
  adapter disconnects ungracefully, so downstream consumers learn the adapter
  is down instead of silently missing data. Empty will topic disables the LWT
  (the default for local dev).

The will is registered before `connect()` via `client.will_set(...)`. The
subscription uses `client.subscribe(topic, qos=settings.mqtt_qos)`.

Tests: `tests/test_mqtt_qos_will.py` (recording fake paho client, no broker).

## Related

- [[20_Architecture/Edge Ingest Backpressure]]
- [[20_Architecture/Schema Governance]]
- `comparission.md` pillar 05
