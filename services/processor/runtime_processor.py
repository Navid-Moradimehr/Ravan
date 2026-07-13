from __future__ import annotations

import logging
import json
import os
import signal
import time

from confluent_kafka import Consumer, Producer, TopicPartition
from prometheus_client import start_http_server
from services.common.brokers import resolve_kafka_brokers
from services.common.normalize import normalize_runtime_event
from services.common.runtime_metrics import set_consumer_lag
from services.common.runtime_event import RollingWindowState, RuntimeEventRecord
from services.common.threshold_policy import resolve_threshold_policy
from services.common.threshold_policy_sync import start_policy_sync_workers
from services.edge_ingest.model import to_json_bytes
from services.historian.client import insert_processed_event, insert_processed_events
from services.processor.runtime_pipeline import build_runtime_event_payload
from services.processor.scoring import score_event

PRUNE_EVERY_N_MESSAGES = 128

logger = logging.getLogger(__name__)


def should_persist_processed() -> bool:
    """Whether the runtime processor writes processed events to the historian.

    Mirrors the Flink job's ``FLINK_PERSIST_PROCESSED_EVENTS`` gate so both
    execution paths can be toggled independently. Defaults to enabled to
    preserve the historical Python-processor behavior; set
    ``RUNTIME_PERSIST_PROCESSED_EVENTS=0`` to keep the processor as a pure
    topic fan-out (offsets are still committed after a successful produce).
    """
    return os.getenv("RUNTIME_PERSIST_PROCESSED_EVENTS", "1").strip().lower() in {"1", "true", "yes"}


def _flush_processed_batch(
    buffer: list[dict[str, object]],
    offsets: list[tuple[str, int, int]],
    *,
    force: bool,
    db_batch_size: int,
    db_flush_seconds: float,
    last_db_flush: float,
    persist_processed: bool,
    insert_batch,
    insert_single,
    commit_offsets,
) -> float:
    """Flush the processed-event buffer, optionally persisting to the historian.

    Returns the updated ``last_db_flush`` monotonic timestamp. When
    ``persist_processed`` is False the historian write is skipped entirely but
    offsets are still committed after the buffered batch is drained, so the
    processor keeps making progress as a pure topic fan-out.
    """
    if not buffer:
        return last_db_flush
    elapsed = time.monotonic() - last_db_flush
    if not force and len(buffer) < db_batch_size and elapsed < db_flush_seconds:
        return last_db_flush

    batch = buffer[:]
    pending_offsets = offsets[:]
    buffer.clear()
    offsets.clear()
    write_failed = False
    if persist_processed:
        try:
            insert_batch(batch)
        except Exception as exc:  # pragma: no cover - logged failure path
            logger.warning("historian processed-event batch write failed: %s", exc)
            write_failed = True
            for event in batch:
                try:
                    insert_single(event)
                except Exception as inner_exc:
                    logger.warning("historian processed-event fallback write failed: %s", inner_exc)
                    write_failed = True
    if (not write_failed) and pending_offsets:
        try:
            commit_offsets(
                [TopicPartition(topic, partition, offset + 1) for topic, partition, offset in pending_offsets]
            )
        except Exception as exc:  # pragma: no cover - coordinator/runtime failure path
            logger.warning("processor offset commit failed: %s", exc)
    return time.monotonic()


def _prune_windows(
    windows: dict[str, RollingWindowState],
    last_seen: dict[str, float],
    max_devices: int,
    max_idle_seconds: int,
    now_ts: float,
) -> int:
    removed = 0
    if max_devices <= 0 and max_idle_seconds <= 0:
        return removed

    if max_idle_seconds > 0:
        stale_ids = [device_id for device_id, ts in last_seen.items() if now_ts - ts > max_idle_seconds]
        for device_id in stale_ids:
            windows.pop(device_id, None)
            last_seen.pop(device_id, None)
            removed += 1

    if max_devices > 0 and len(last_seen) > max_devices:
        for device_id, _ in sorted(last_seen.items(), key=lambda item: item[1])[: len(last_seen) - max_devices]:
            windows.pop(device_id, None)
            last_seen.pop(device_id, None)
            removed += 1

    return removed


def main() -> None:
    start_http_server(int(os.getenv("PROCESSOR_METRICS_PORT", "8094")))
    policy_stop, _policy_threads = start_policy_sync_workers(
        role="python-processor",
        enable_relay=False,
    )
    brokers = resolve_kafka_brokers("localhost:19092")
    input_topic = os.getenv("IOT_TOPIC", os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized"))
    output_topic = os.getenv("PROCESSED_TOPIC", "iot.processed")
    progress_every = int(os.getenv("PROCESSOR_PROGRESS_EVERY", "1000"))
    window_limit = max(1, int(os.getenv("RUNTIME_WINDOW_LIMIT", "25")))
    db_batch_size = max(1, int(os.getenv("RUNTIME_DB_BATCH_SIZE", "1024")))
    db_flush_seconds = float(os.getenv("RUNTIME_DB_FLUSH_SECONDS", "1.0"))
    max_idle_seconds = int(os.getenv("RUNTIME_DEVICE_MAX_IDLE_SECONDS", "0"))
    max_devices = int(os.getenv("RUNTIME_MAX_ACTIVE_DEVICES", "0"))
    running = True
    windows: dict[str, RollingWindowState] = {}
    window_last_seen: dict[str, float] = {}
    processed_buffer: list[dict[str, object]] = []
    processed_offsets: list[tuple[str, int, int]] = []
    last_db_flush = time.monotonic()

    persist_processed = should_persist_processed()

    def flush_processed_buffer(force: bool = False) -> None:
        nonlocal last_db_flush
        last_db_flush = _flush_processed_batch(
            processed_buffer,
            processed_offsets,
            force=force,
            db_batch_size=db_batch_size,
            db_flush_seconds=db_flush_seconds,
            last_db_flush=last_db_flush,
            persist_processed=persist_processed,
            insert_batch=insert_processed_events,
            insert_single=insert_processed_event,
            commit_offsets=lambda offsets: consumer.commit(offsets=offsets, asynchronous=False),
        )

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    consumer = Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": "runtime-iot-processor",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    producer = Producer({"bootstrap.servers": brokers, "client.id": "runtime-iot-processor"})
    consumer.subscribe([input_topic])

    processed = 0
    started_at = time.time()

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                logger.warning("consumer_error=%s", message.error())
                continue
            try:
                low, high = consumer.get_watermark_offsets(TopicPartition(message.topic(), message.partition()), cached=True)
                if high >= 0:
                    set_consumer_lag("processor", message.topic(), message.partition(), high - (message.offset() + 1))
            except Exception:
                pass

            raw_event = json.loads(message.value().decode("utf-8"))
            event = RuntimeEventRecord.from_raw_mapping(raw_event)
            # Keep the fallback runtime keyed exactly like Flink. A device can
            # expose multiple tags and can appear in multiple source scopes;
            # using only asset/device_id mixes unrelated rolling windows.
            processing_key = event.partition_key().decode("utf-8")
            now_ts = time.time()
            device_window = windows.get(processing_key)
            if device_window is None:
                device_window = RollingWindowState(maxlen=window_limit)
                windows[processing_key] = device_window

            window_last_seen[processing_key] = now_ts
            temperature_avg, vibration_avg, window_size = device_window.append(event)
            policy = resolve_threshold_policy(event.site_id, event.asset_id, event.tag)
            threshold_result = None
            processed_event = build_runtime_event_payload(
                event,
                temperature_avg_c=temperature_avg,
                vibration_avg_mm_s=vibration_avg,
                window_size=window_size,
                threshold_policy=policy,
                threshold_result=threshold_result,
            )

            producer.produce(
                output_topic,
                key=event.partition_key(),
                value=to_json_bytes(processed_event),
            )
            # Drain delivery reports periodically instead of on every message;
            # per-message poll(0) is a syscall that throttles high-throughput
            # ingest. The producer.flush(10) in the finally block covers shutdown.
            if processed % PRUNE_EVERY_N_MESSAGES == 0:
                producer.poll(0)
            processed_buffer.append(processed_event)
            processed_offsets.append((message.topic(), message.partition(), message.offset()))
            flush_processed_buffer()
            processed += 1

            if processed % PRUNE_EVERY_N_MESSAGES == 0 and (max_devices > 0 or max_idle_seconds > 0):
                removed_windows = _prune_windows(windows, window_last_seen, max_devices, max_idle_seconds, now_ts)
                if removed_windows:
                    print(f"pruned_windows={removed_windows} active_devices={len(windows)}")

            if progress_every > 0 and processed % progress_every == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"processed={processed} rate={processed / elapsed:.1f}/sec topic={output_topic}")
    finally:
        policy_stop.set()
        flush_processed_buffer(force=True)
        consumer.close()
        producer.flush(10)


if __name__ == "__main__":
    main()
