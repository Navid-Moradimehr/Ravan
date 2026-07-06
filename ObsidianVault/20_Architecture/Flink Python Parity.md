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
