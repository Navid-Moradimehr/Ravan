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

The edge layer now batches historian writes instead of inserting each event
individually on the ingest hot path. The processor and Flink job also share
the same enrichment contract so severity labels stay aligned across execution
paths and the distributed Flink runtime can emit the same output shape.

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
- `services/processor/scoring.py` is the shared scoring contract for the runtime processor and Flink job.
- `services/processor/runtime_pipeline.py` applies the shared runtime enrichment and serialized payload contract used by both execution paths.


## Dataset Replay Path

External datasets can be injected into the pipeline via the dataset replayer:

- `data/benchmarks/industrial_mixed_benchmark.csv` is a local mixed-protocol benchmark pack for replay and load testing.



This allows real-world benchmark data (e.g., AI4I 2020, NASA C-MAPSS) to flow through the same normalization, processing, and enrichment stages as live protocol data.

Distributed runtime note:

- The host-run Python processor remains the lightweight fallback for local development and direct benchmark work.
- The Flink job in `services/processor/iot_anomaly_job.py` keys the stream by asset identity, maintains rolling state per key, and checkpoints state so the processor can be scaled horizontally in a real deployment.
- Site profiles now carry an explicit `runtime.mode` value so operators can keep `python-fallback` for development sites, `flink-local` for plant-local deployments, and `flink-production` for multi-site rollouts.
- The new `production-pipeline` benchmark command measures the selected runtime mode directly, which makes the fallback versus Flink gap visible in one report.
- `datastreamd up` now uses `runtime.mode` to decide whether it launches the legacy Python processor or the Flink job by default.
- Helm deployments and generated site bundles now follow the same runtime-mode contract, so a plant-local or federated export renders the Flink job instead of the fallback processor path.
## Runbook

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-industrial-sim.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/edge-soak.ps1 -Seconds 300 -MqttRatePerSecond 100
```

## Production Boundary

This layer mirrors real gateway behavior. It does not auto-discover or directly control plant hardware. Real deployments should connect configured OPC UA endpoints, MQTT brokers, or Modbus TCP devices through a secured edge gateway or SCADA/IIoT runtime.
