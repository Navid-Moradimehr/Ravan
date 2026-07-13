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

### Replay execution

The historian replay endpoint now launches a managed background producer for
the built-in mock dataset. It publishes canonical events to
`industrial.normalized`, reports acknowledged event counts and progress, and
supports cancellation. External CSV datasets can be enabled with
`DATASET_REPLAY_PATHS`, a JSON mapping of dataset IDs to files visible to the
API container. A replay is deliberately not presented as completed until the
Kafka producer flushes successfully.

### Processing-key parity

Python fallback windows now use the same composite stream partition key as the
Flink job. Interleaved tags, sources, assets, and sites therefore do not share
state accidentally when the fallback runtime is used.

### Edge delivery and malformed records

Store-and-forward records are removed only after their Kafka delivery callback
acknowledges them. Failed callbacks remain on disk for a later replay. The
normalized and AI fan-outs publish malformed Kafka payloads to
`industrial.dlq`, flush the DLQ producer, and commit the source offset only
after the DLQ write succeeds.

### Typed historian values

`industrial_events` preserves the canonical scalar type through
`value_type`, `value_text_raw`, and `value_bool` while retaining the numeric
`value` column for existing trend and SQL consumers. Older installations may
already have a generated `value_text` column; the migration leaves that
column intact and adds `value_text_raw` rather than attempting a destructive
hypertable rewrite. Non-numeric measurements are no longer forced through
`float()` at the historian boundary.

Historian UUID columns also accept external event IDs such as `evt-808070`:
valid UUIDs are preserved and other IDs are converted to deterministic UUID5
values. Sparse protocol records receive stable `unknown`/`value` dimension
defaults at the storage boundary instead of crashing a fan-out process.

### Durable local Flink state

Compose provisions a named `flink-checkpoints` volume and initializes its
ownership before JobManager and TaskManager start. The Flink job reads
`FLINK_CHECKPOINT_DIR` and `FLINK_SAVEPOINT_DIR`; Kubernetes or multi-site
deployments must replace the local file URI with a durable shared or
S3-compatible location.

## Remaining deployment-owned work

The following are intentionally not hidden behind application code:

- Source connection credentials, authentication/authorization, and site
  network access remain adopter-owned.
- Source connection changes still require an edge restart; hot connector
  reconciliation is deferred until a deployment needs it.
- Kubernetes operators must provide durable checkpoint/savepoint storage and
  set the corresponding Flink environment variables.
- External lakehouse, S3/MinIO retention, backup policy, GPU sizing, and
  multi-site federation remain deployment choices.
- Real PLC timing, protocol certification, and plant acceptance still require
  hardware or a vendor simulator; local simulation cannot certify a physical
  installation.

## Verification

- Targeted hardening tests: `32 passed`
- Full backend suite after this change: `572 passed`
- Frontend production build: passed
- The previous scaled 15-minute report marked a run passed while showing
  `175361` AI consumer lag. The new acceptance logic correctly treats that as
  a failed campaign.

Current verification for this change:

- Python compilation: passed.
- Docker Compose configuration validation: passed.
- Docker Flink REST job overview: `iot-anomaly-processor` running with two
  active tasks after checkpoint volume initialization.
- Timescale migration: completed successfully; existing data volume retained
  and typed columns present. Legacy generated `value_text` installations are
  supported through the additive `value_text_raw` migration.
- Docker projection smoke: `fanout` and `processed-fanout` remained running;
  the running volume contained `61,247` recent industrial rows and `30,085`
  recent processed rows during verification.

## Architecture boundary

The platform owns event contracts, Kafka topic semantics, deterministic
processing, historian projections, replay contracts, and benchmark gates.
Users own credentials, authentication and authorization, physical PLC/site
networking, retention policy, GPU sizing, and external lakehouse operations.
