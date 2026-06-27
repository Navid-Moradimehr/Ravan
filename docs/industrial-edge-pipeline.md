# Industrial Edge Pipeline

## Purpose

The edge layer makes the app closer to a real industrial deployment without requiring physical PLCs, sensors, or plant-network access.

## Data Flow

```text
OPC UA simulator ------+
MQTT broker/publisher -+--> edge-ingest --> industrial.raw --> industrial.normalized
Modbus TCP simulator --+                                           |
                                                                  v
                                                               iot.raw --> processor --> iot.processed --> ai-gateway
```

## Envelope

Every normalized event includes:

- `event_id`
- `source_protocol`
- `source_id`
- `asset_id`
- `tag`
- `value`
- `quality`
- `unit`
- `site`
- `line`
- `ts_source`
- `ts_ingest`
- `schema_version`

Invalid records are published to `industrial.dlq`.

Shared normalization behavior note:

- `services/common/normalize.py` is used by both edge ingestion and runtime processing to map inbound events into the processor compatibility shape.


## Dataset Replay Path

External datasets can be injected into the pipeline via the dataset replayer:



This allows real-world benchmark data (e.g., AI4I 2020, NASA C-MAPSS) to flow through the same normalization, processing, and enrichment stages as live protocol data.
## Runbook

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-industrial-sim.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/edge-soak.ps1 -Seconds 300 -MqttRatePerSecond 100
```

## Production Boundary

This layer mirrors real gateway behavior. It does not auto-discover or directly control plant hardware. Real deployments should connect configured OPC UA endpoints, MQTT brokers, or Modbus TCP devices through a secured edge gateway or SCADA/IIoT runtime.
