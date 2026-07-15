# Model Evidence Lakehouse Routing

## Purpose

The platform keeps three evidence families distinct:

- Telemetry is normalized scalar data for historian and stream processing.
- Operational events record actions, outcomes, maintenance, context, and
  episode boundaries.
- Observation artifacts are immutable references to large media or tensor
  objects stored outside Kafka.

## Runtime path

`industrial.normalized` -> historian and optional telemetry lakehouse

`industrial.operational` -> optional operational-fanout -> `operational_events`

`POST /api/v1/observation-artifacts` ->
`industrial.observation-artifacts` -> optional artifact-fanout ->
`observation_artifacts`

Operational and artifact rows are not coerced into telemetry records. This is
important for training datasets because an action is not a measurement and an
image reference is not a numeric sensor value.

## Ownership

The platform owns schemas, Kafka publication, routing, and deterministic
archive behavior. Users own object-store credentials, media upload, retention,
encryption, access policy, compaction, and the semantic meaning of rewards or
control actions.

## Deployment

Both archive consumers are optional `extended` Compose services. The default
historian and normalized telemetry path remains usable without MinIO or a
lakehouse. Use the same Iceberg catalog and warehouse settings for S3 or
MinIO, and use a separate table name for each event family.
