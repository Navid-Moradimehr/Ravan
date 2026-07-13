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
- Historian replay now runs a real Kafka producer for the built-in mock dataset
  and reports acknowledged progress; external CSV replay is opt-in through
  `DATASET_REPLAY_PATHS`.
- Python fallback windows now use the same composite stream key as Flink.
- Edge store-and-forward entries remain on disk until Kafka delivery is
  acknowledged.
- Malformed normalized and AI records are sent to the acknowledged
  `industrial.dlq` path before source offsets are committed.
- Historian ingestion preserves numeric, boolean, and string scalar values in
  `value_type`, `value_text_raw`, and `value_bool` while retaining the
  existing numeric query column. The migration is compatible with older
  generated `value_text` columns.
- External event IDs are normalized deterministically when UUID-backed
  historian tables receive IDs such as `evt-808070`; sparse protocol records
  receive stable storage-boundary defaults.
- Compose provisions and initializes a durable named Flink checkpoint volume.

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

## Remaining deployment-owned risks

Live source reconciliation still requires an edge restart. Kubernetes must
provide durable shared or S3-compatible checkpoint storage. Credentials,
authN/authZ, plant networking, external lakehouse retention, GPU sizing, and
physical PLC certification remain adopter-owned. These are deployment
boundaries, not missing local code paths.

## Verification

- `32` targeted hardening tests passed.
- Full backend suite passed: `572` tests.
- Python compilation passed.
- Docker Compose configuration validation passed.
- Flink REST reported `iot-anomaly-processor` as `RUNNING` with two active
  tasks after the checkpoint volume initializer completed.
- Timescale migration completed successfully against the running Compose
  volume.
- Docker projection smoke remained stable with both `fanout` and
  `processed-fanout` running and recent historian rows written.

## Ownership

The platform owns Kafka/event contracts, deterministic processing, historian
projections, and benchmark gates. Deployers own secrets, authN/authZ, physical
PLC connectivity, retention, GPU sizing, and external storage policy.
