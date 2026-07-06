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
- Phase 5: the `lakehouse` sink (`services/sinks/lakehouse.py`) writes normalized
  events to an Iceberg table on MinIO via `pyiceberg` + `pyarrow` (ADR 0003).

## Delivery Semantics and Dedup (added 2026-07-06)

> Competitive inspiration 3 (pillar 06 - exactly-once end-to-end / chaos tests).

The fan-out consumer provides **at-least-once** delivery to sinks:

1. Idempotent Kafka producers + `acks=all`.
2. `enable.auto.commit=False` - offsets are committed **only after** the sink
   `write_batch` + `flush` succeeds (see `normalized_fanout.py:flush()`).
3. If the consumer crashes between poll and commit, Kafka rebalances and
   redelivers from the last committed offset - so a sink may see the same
   `event_id` more than once.

The de-facto **exactly-once** strategy is `event_id` dedup at the historian:
both `insert_industrial_event` and `insert_industrial_events` use
`ON CONFLICT (event_id) DO NOTHING`, so a redelivered event is a no-op instead
of a duplicate row. This is the open-source-friendly alternative to broker
transactions / two-phase commit.

### Chaos / replay tests

`tests/test_delivery_chaos.py` (3 cases) makes this contract explicit:

- Mid-batch crash + redelivery -> same `event_id`s written twice, but every
  batch SQL carries `ON CONFLICT (event_id) DO NOTHING`.
- Crash before commit -> offset uncommitted, message redelivered on restart,
  offset commits only after the successful second attempt.
- Duplicate `event_id` within one batch -> resolved by the DB constraint.

The tests use a recording fake Kafka consumer (redelivers on `reset_to`) and a
stubbed historian client, so they run without a real broker or database.

## Related

- [[20_Architecture/Schema Governance]]
- [[20_Architecture/Industrial Edge Pipeline]]
- `comparission.md` pillar 06
