# Data Integrity Contract

The platform treats Kafka as the replay boundary and preserves event identity,
source time, source/site/asset context, quality, units, scalar type, and lineage
through processing and storage. A successful event is not considered delivered
merely because a producer call returned or a consumer parsed it.

## Pipeline Guarantees

1. Protocol connectors create a canonical `IndustrialEvent`. Validation rejects
   missing identity, invalid or timezone-naive source timestamps, and non-finite
   numeric values before normalized publication.
2. OPC UA ingestion reads the server `DataValue`, preserving the source
   timestamp and mapping the StatusCode to `good`, `uncertain`, or `bad`.
3. The edge producer uses idempotent Kafka production and tracks outstanding
   delivery callbacks. On shutdown, unresolved messages are written to the
   configured disk spool; without a spool, shutdown fails visibly instead of
   claiming success.
4. Kafka retains the normalized event as the replayable source. Consumer offsets
   are committed only after a successful sink write or acknowledged DLQ write.
5. Flink and the Python fallback use the same `RuntimeEventRecord` and enrichment
   contract. Malformed normalized records fail visibly rather than being
   checkpointed as successful.
6. Historian single and batch writes use source/event time and idempotent
   `(time, event_id)` conflict handling.
7. Numeric, boolean, and string scalar values retain their original type.
   Nonnumeric values are not represented as real zero measurements.
8. Legacy multi-measurement frames retain device identity, temperature,
   vibration, and pressure and are explicitly marked `value_type=composite` and
   `tag=__composite__`.
9. The lakehouse telemetry row retains the exact canonical event in
   `payload_json`; its numeric projection is null for nonnumeric values.

## Failure Behavior

- Invalid connector events are actionable source errors or DLQ records.
- A durable sink failure leaves offsets replayable. The Flink historian sink
  fails the task if both batch and per-record writes fail.
- At-least-once replay can repeat delivery attempts. Historian event identity
  prevents duplicates when event ID and source time remain stable.
- A poison record written directly to a normalized topic by an external
  producer can stop/restart its Flink partition until the operator corrects or
  removes it. External producers must comply with the canonical contract.

## Verification Evidence (2026-07-16)

- Full Python regression suite: `696 passed`.
- Focused integrity suite: `73 passed`; final historian/Flink checks: `30 passed`.
- Docker Flink job: `RUNNING`, `2/2` tasks.
- Live event-level probe: numeric, boolean, string lifecycle, and composite
  records matched across `industrial_events` and `processed_events`, including
  event ID, source timestamp, identity, quality, scalar type, and measurements.
- Native connector sample: 881 OPC UA records from two source identities in five
  minutes, with zero non-good samples and no pipeline errors in the inspected
  logs.

## Limits Of This Evidence

This contract does not certify proprietary PLC firmware, field wiring, network
timing, vendor gateway transformations, certificate infrastructure, or an
external object store. Those boundaries require site acceptance tests with the
operator's devices and storage. The platform cannot detect a physically wrong
sensor value that is valid according to the configured schema; calibration,
engineering limits, and source mapping remain deployment-owned.

