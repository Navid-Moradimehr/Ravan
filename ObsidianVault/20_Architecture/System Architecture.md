# System Architecture

```text
Ingestion           Broker             Processing                     Insight
---------           ------             ----------                     -------
Mock IoT  --> Kafka --> PyFlink / Python fallback --> AI Gateway
Postgres --> Debezium --> CDC topics   keyed state + rules            LLM summaries
```

## Components

- Kafka provides the broker layer and the platform keeps schema validation inside application code.
- PyFlink owns the distributed keyed-state runtime path.
- The Python processor stays available as the local fallback and benchmark harness with the same enrichment contract.
- FastAPI AI Gateway owns OpenAI-compatible and open-weight LLM calls with async batching.
- Prometheus and Grafana expose platform health and latency.
- Next.js dashboard provides a control-room view over the local platform.
- The logical metadata plane is read-only and aggregates platform registries and catalogs without creating a new service boundary.
- Operational memory is read-only for now and exposes alerts, annotations, shifts, reports, and backup readiness without turning the platform into a MES.


## Normalized Fan-Out Data Flow

```text
Edge adapters (MQTT/OPC UA/Modbus)
        |
        v
  EdgePublisher --> industrial.raw (legacy, deprecated)
        |       \--> industrial.normalized
        |       \--> iot.raw (legacy)
        v
  Kafka: industrial.normalized
        |
        +--> Normalized fan-out consumer --> CompositeSink
        |                                     |-- TimescaleHistorianSink
        |                                     |-- KafkaSink
        |                                     \-- LakehouseSink (Phase 5)
        |
        +--> runtime processor --> iot.processed + processed_events
        \--> Flink job --> iot.processed
```

The edge publisher produces only to Kafka; the normalized fan-out consumer owns
historian persistence via sinks. This decouples the edge path from specific
endpoint datasets so the open-source platform can target different endpoints
(history, lakehouse, dashboards) through configuration.

## Data Classification

- **Raw industrial data**: edge adapters -> EdgePublisher -> `industrial.raw` /
  `iot.raw` (untyped envelopes, pre-validation).
- **Normalized + validated data**: `industrial.normalized` (validated
  IndustrialEvent envelopes) -> fan-out consumer -> sinks (historian,
  lakehouse). Also consumed by the runtime processor and Flink job.
- **Metadata**: semantic plane (ontology, entities, relationships) and schema
  governance flow through the semantic tables, separate from the time-series
  path.
- **Processed / scored data**: `iot.processed` and `processed_events`
  (anomaly-scored, windowed) from the runtime processor / Flink job.


## AI-Enriched Persistence

The AI gateway consumes `iot.processed`, enriches batches via the LLM, and
produces `iot.ai_enriched`. The `ai_enriched_fanout` consumer
(`services/processor/ai_enriched_fanout.py`) persists those summaries to the
historian `ai_enriched` table with at-least-once delivery, so the gateway stays
decoupled from the endpoint dataset.

## Push-Driven Dashboard Bus

The dashboard SSE/WS stream was refreshed by a fixed 2-second DB poll. It is now
push-driven: the `historian_broadcast_loop` waits on a refresh event that
`enrich_batch` sets after each successful enrichment, waking subscribers
immediately on change (with a 5-second fallback). This removes the constant DB
load of periodic polling.


## Topic & Schema Provisioning (2026-07-06)

- **Topics auto-created by compose.** The `kafka-init` one-shot service
  (`docker/docker-compose.yml`, commit `8ea9d29`) creates all six canonical
  topics idempotently on first `docker compose up`:
  `industrial.raw`, `industrial.normalized`, `industrial.dlq`, `iot.raw`,
  `iot.processed`, `iot.ai_enriched` (3 partitions, replication-factor 1). The
  PowerShell scripts under `scripts/` remain as manual fallbacks for non-compose
  brokers and are now aligned with this canonical set.
- **Single schema source of truth.** The historian schema is
  `docker/postgres/init-timescale-full.sql` (unique `*_event_id_uniq` indexes +
  hypertables), mounted by the `timescaledb` service. The Debezium `orders` CDC
  demo schema is `docker/postgres/init.sql`, mounted by the separate `postgres`
  service. Both mounts were corrected in `ffc4e07` (they previously pointed at
  non-existent `./postgres/` paths, which silently mounted empty dirs).

## Runtime Processor Historian Gate

The Python runtime processor (`services/processor/runtime_processor.py`) and the
Flink job (`services/processor/iot_anomaly_job.py`) now have symmetric control
over historian persistence:

- Python: `RUNTIME_PERSIST_PROCESSED_EVENTS` (default `1`, commit `b6eca10`).
- Flink: `FLINK_PERSIST_PROCESSED_EVENTS` (default off).

When the Python gate is off, the processor still produces to `iot.processed` and
commits offsets, but skips the `processed_events` historian write - letting
open-source operators run it as a pure topic fan-out when their endpoint is a
lakehouse or a non-Timescale store. See [[20_Architecture/Sink Architecture]].
