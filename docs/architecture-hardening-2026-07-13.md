# Architecture Hardening: 2026-07-13

This change set addresses release-blocking wiring and acceptance defects found
in the architecture review. It does not change the platform's security model:
authentication, authorization, secrets, and site infrastructure remain
deployment-owned by adopters.

## Implemented

### Canonical processing topic

The default Python and Flink runtimes now consume `industrial.normalized`.
`iot.raw` remains available only as an explicit legacy override through
`IOT_TOPIC`. Dataset replay and connector traffic therefore follow the same
processing path by default.

### Independent processed historian projection

Flink publishes deterministic results to `iot.processed`. The new
`processed-fanout` Compose service consumes that topic and writes
`processed_events` to TimescaleDB. This keeps Flink independent of the
historian and allows historian recovery without restarting stream processing.

The projection is at-least-once and relies on historian idempotency. It is not
claimed to be end-to-end exactly-once.

### Clean Compose initialization

Database initialization mounts are relative to `docker/docker-compose.yml`:

```text
./postgres/init.sql
./postgres/init-timescale-full.sql
```

Clean-volume installation tests now verify these paths and the processed
projection service.

### REST ingestion delivery

REST event variants are queued on one Kafka producer and flushed as one bundle
instead of performing three separate flushes. Successful ingestion lineage is
recorded after Kafka delivery succeeds. A delivery timeout returns
`publish_failed`.

### AI delivery acknowledgement

The AI gateway waits for the generated Kafka event to be acknowledged before
committing the source offsets. This remains at-least-once and requires
idempotent downstream persistence.

### Benchmark acceptance

Industrial soak reports now fail when any observed consumer group exceeds the
configured `acceptance.max_consumer_lag`, even if an aggregate lag query is
zero or unavailable. This prevents an AI or secondary sink backlog from being
hidden by an aggregate metric.

The default scenario uses `max_consumer_lag: 0`, which means the final drain
must reach zero for every observed consumer.

## Still open

These items were not hidden by this change and remain follow-up work:

- Replay API state is still a control-plane scaffold; it does not yet launch a
  managed dataset producer.
- Python and Flink need a shared asset-level versus tag-level processing-key
  decision and parity fixtures for interleaved multi-site signals.
- Edge store-and-forward still needs delivery-callback-based spool removal.
- Malformed Kafka records need an acknowledged DLQ path instead of a log-and-
  skip path.
- Historian value storage is numeric-only while the canonical model permits
  strings and booleans. The contract must either become numeric-only or gain
  typed value columns.
- Compose Flink checkpoints need a durable host volume; Kubernetes deployments
  need a durable S3-compatible checkpoint location.
- Source connection changes still require an edge restart and credential
  resolution remains deployment-owned.

## Verification

- Targeted hardening tests: `29 passed`
- Full backend suite before this change: `566 passed`
- Frontend production build: passed
- The previous scaled 15-minute report marked a run passed while showing
  `175361` AI consumer lag. The new acceptance logic correctly treats that as
  a failed campaign.

## Architecture boundary

The platform owns event contracts, Kafka topic semantics, deterministic
processing, historian projections, replay contracts, and benchmark gates.
Users own credentials, authentication and authorization, physical PLC/site
networking, retention policy, GPU sizing, and external lakehouse operations.
