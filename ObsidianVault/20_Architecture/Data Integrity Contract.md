# Data Integrity Contract

Status: implemented and locally verified on 2026-07-16.

Canonical device data crosses these durability boundaries:

`connector -> validation -> idempotent Kafka publication -> Flink/Python runtime -> fan-out -> historian/lakehouse`

## Preserved Context

- event ID and lineage
- source, site, line, asset, and tag
- source timestamp and quality
- unit and schema version
- numeric, boolean, or string scalar type
- temperature, vibration, and pressure in legacy composite frames

## Failure Rule

No consumer should commit a Kafka offset before its durable sink succeeds or an
acknowledged DLQ record exists. Flink historian failures must fail and replay,
not clear the buffer. Edge shutdown must spool unresolved delivery callbacks or
fail visibly.

## Evidence

- [[Local Validation Evidence 2026-07-16]]
- `696` full regression tests passed
- four-shape live integrity probe matched raw and processed historian rows
- Flink remained running with both tasks
- native OPC UA traffic continued without pipeline log errors

## Boundaries

Real PLC firmware, calibration, field wiring, vendor gateway mappings, external
object stores, and plant networking still require operator acceptance testing.
The platform validates configured meaning; it cannot infer that a plausible
sensor value is physically correct.

Related: [[System Architecture]], [[Schema Governance]], [[Sink Architecture]],
[[Source Onboarding Runtime]].
