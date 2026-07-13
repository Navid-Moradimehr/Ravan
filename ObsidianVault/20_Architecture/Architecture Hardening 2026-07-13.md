# Architecture Hardening 2026-07-13

## Status

Implemented and verified in the source repository. This note records the
current contract after the architecture audit.

## Changes

- Default Flink and Python processing input: `industrial.normalized`.
- `iot.raw` is a legacy explicit override only.
- `iot.processed` is persisted by the independent `processed-fanout`
  projection rather than by Flink itself.
- Compose database mounts now resolve correctly from the `docker` directory.
- REST ingestion publishes its raw, normalized, and compatibility records in
  one acknowledged producer batch.
- Ingestion lineage is recorded after successful Kafka delivery.
- AI input offsets are committed only after the AI output is acknowledged.
- Soak tests now evaluate per-consumer lag, not only an aggregate lag query.

## Data-flow contract

```text
connector/API
  -> industrial.raw
  -> industrial.normalized
  -> Flink
  -> iot.processed
  -> processed-fanout
  -> TimescaleDB processed_events
```

The normalized historian fanout remains independent and continues to write
the hot telemetry historian. AI remains an optional downstream consumer.

## Remaining risks

Replay execution, shared Python/Flink processing-key semantics, delivery-aware
edge spooling, malformed-record DLQ acknowledgement, typed historian values,
durable Compose checkpoints, and live source reconciliation remain open. They
are tracked as follow-up work rather than represented as complete features.

## Ownership

The platform owns Kafka/event contracts, deterministic processing, historian
projections, and benchmark gates. Deployers own secrets, authN/authZ, physical
PLC connectivity, retention, GPU sizing, and external storage policy.
