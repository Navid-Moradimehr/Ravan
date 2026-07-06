# Flink / Python Runtime Parity

## Problem

The Python runtime processor and the Flink job had three divergences:

1. The Python processor persisted `processed_events` to the historian; the Flink
   job only wrote to the `iot.processed` Kafka topic (no historian persistence).
2. The Flink keyed state cleared and re-added the full sample list on every
   element (O(window) state rewrite per event).
3. The Flink key-by used asset-id only, while the rest of the platform uses a
   7-field composite key.

## Fixes

- **ProcessedEventsSink**: a Flink `SinkFunction` that batches processed
  payloads and writes them to the historian (`insert_processed_events` with
  per-event fallback). Activated by `FLINK_PERSIST_PROCESSED_EVENTS=1`.
- **State eviction**: only rewrite the list state when an eviction actually
  occurred; otherwise append the new sample.
- **Composite key**: `_partition_key` now uses
  `services.common.stream_scope.stream_partition_key` (project|site|line|
  protocol|source|asset|tag).

## Batched Producer Drain

The Python runtime processor now calls `producer.poll(0)` every 128 messages
instead of on every message, removing a per-message syscall. Shutdown still
calls `producer.flush(10)`.

## Settings

- `FLINK_PERSIST_PROCESSED_EVENTS` (default off)
- `FLINK_PROCESSED_BATCH_SIZE` (default 512)

## Checkpoint and State-Backend Config (added 2026-07-06)

> Competitive inspiration 4 (pillar 02 - Flink stateful depth).

The Flink job previously used in-memory (hashmap) state with
`AT_LEAST_ONCE` delivery and bare `enable_checkpointing(interval)`. On a job
failure or restart it lost all keyed window state and replayed from the source.

`configure_checkpoints()` now sets a production-grade checkpoint + state-backend
profile via `CheckpointSettings` (read from env vars):

- **Mode**: exactly-once (default) - aligned checkpoints, no duplicate output on
  failover.
- **State backend**: RocksDB (default) - off-heap keyed state, so window state is
  not bounded by task-manager RAM and the job scales horizontally.
- **Incremental checkpoints**: on by default when RocksDB is selected - only
  changed state is persisted, cutting checkpoint size and time.
- **Externalized retained checkpoints**: a cancelled/stopped job keeps its last
  checkpoint so a restart resumes from it instead of a cold start.
- **Min pause / max concurrent / timeout**: tuned defaults (500ms / 1 / 600s).

### Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `FLINK_CHECKPOINT_INTERVAL_MS` | 10000 | 0 disables checkpointing |
| `FLINK_CHECKPOINT_MODE` | exactly_once | at_least_once alternative |
| `FLINK_CHECKPOINT_TIMEOUT_MS` | 600000 | |
| `FLINK_CHECKPOINT_MIN_PAUSE_MS` | 500 | |
| `FLINK_CHECKPOINT_MAX_CONCURRENT` | 1 | |
| `FLINK_CHECKPOINT_EXTERNALIZED_CLEANUP` | retain | delete alternative |
| `FLINK_CHECKPOINT_UNALIGNED` | false | true helps backpressure |
| `FLINK_STATE_BACKEND` | rocksdb | hashmap alternative |
| `FLINK_INCREMENTAL_CHECKPOINTS` | true (rocksdb) | false (hashmap) |

`CheckpointSettings` + `checkpoint_settings()` are pure-Python and unit-tested
without PyFlink. `configure_checkpoints()` runs only inside the Flink container
(`PYFLINK_AVAILABLE` guard). RocksDB ships with the Flink 1.20 base image; no
extra jar is required.

Tests: `tests/test_flink_checkpoint_config.py` (10 cases).

## Related

- [[20_Architecture/Sink Architecture]]
- `comparission.md` pillar 02
