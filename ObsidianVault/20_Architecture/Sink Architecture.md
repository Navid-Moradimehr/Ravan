# Sink Architecture

## Problem

The processor wrote directly to the historian (TimescaleDB) and to Kafka topics.
That couples the processing path to specific endpoints and makes it hard to
support different downstream datasets (lakehouse, operational dashboards,
third-party systems) in an open-source context where users bring their own
endpoints.

## Design

```
normalized events (batch)
        |
        v
  CompositeSink
   /    |    \
  v     v     v
Historian  Kafka  Lakehouse
(TimescaleDB) (downstream) (Iceberg/MinIO)
```

- **Sink Protocol**: `write_batch(events) -> int`, `flush()`, `close()`.
- **CompositeSink**: fans one batch to many sinks; per-sink failures are logged
  and isolated so one bad endpoint cannot stall the pipeline.
- **SinkRegistry.from_env()**: builds a composite from `SINKS` (comma-separated
  names). Each sink reads its own env vars.

## Sinks

- `historian` -> `TimescaleHistorianSink` (normalized industrial events to
  TimescaleDB, per-event fallback on batch failure).
- `kafka` -> `KafkaSink` (forward to a downstream topic using the composite
  partition key).
- `lakehouse` -> `LakehouseSink` (Iceberg on MinIO; added in Phase 5).

## Why

Decoupling production from persistence lets the platform target arbitrary
endpoint datasets via configuration instead of code changes. This matches the
open-source requirement that users may have different endpoint datasets.

## Status

- Phase 2: protocol, composite, registry, historian + kafka sinks introduced
  and unit-tested.
- Phase 3: the normalized fan-out consumer (`services/processor/normalized_fanout.py`)
  reads `industrial.normalized` and writes to the composite sink with at-least-once
  delivery (offsets committed only after sink success). The edge publisher no
  longer writes directly to the historian.
