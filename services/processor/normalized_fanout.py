"""Normalized fan-out consumer.

Reads validated/normalized industrial events from ``industrial.normalized`` and
writes them to the configured :class:`~services.sinks.base.CompositeSink`
(historian, lakehouse, downstream Kafka, ...). Offsets are committed only after
the sink batch succeeds, giving at-least-once delivery to endpoint datasets.

This is the decoupling point the architecture needs: the edge publisher no
longer writes directly to the historian; instead it produces the normalized
topic, and this consumer fans the normalized stream out to whatever endpoint
datasets the operator configured via the ``SINKS`` env var.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time

from confluent_kafka import Consumer, TopicPartition

from services.common.brokers import resolve_kafka_brokers
from services.common.runtime_metrics import set_consumer_lag
from services.sinks.base import SinkRegistry

logger = logging.getLogger(__name__)


def main() -> None:
    brokers = resolve_kafka_brokers("localhost:19092")
    input_topic = os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized")
    group_id = os.getenv("FANOUT_GROUP_ID", "normalized-fanout")
    batch_size = max(1, int(os.getenv("FANOUT_BATCH_SIZE", "1024")))
    flush_seconds = float(os.getenv("FANOUT_FLUSH_SECONDS", "1.0"))
    progress_every = int(os.getenv("FANOUT_PROGRESS_EVERY", "1000"))
    # Use latest by default so a restart does not replay the full backlog.
    # Operators can set FANOUT_AUTO_OFFSET_RESET=earliest for explicit replays.
    auto_offset_reset = os.getenv("FANOUT_AUTO_OFFSET_RESET", "latest")
    running = True

    sink = SinkRegistry.from_env()
    if not sink.sinks:
        logger.warning(
            "normalized fan-out started with no sinks (SINKS unset); "
            "events will be consumed and discarded"
        )

    buffer: list[dict[str, object]] = []
    offsets: list[tuple[str, int, int]] = []
    last_flush = time.monotonic()
    processed = 0
    started_at = time.time()

    def flush(force: bool = False) -> None:
        nonlocal last_flush
        if not buffer:
            return
        elapsed = time.monotonic() - last_flush
        if not force and len(buffer) < batch_size and elapsed < flush_seconds:
            return

        batch = buffer[:]
        pending_offsets = offsets[:]
        buffer.clear()
        offsets.clear()

        accepted = sink.write_batch_strict(batch)
        logger.debug("fan-out wrote %d events (%d accepted)", len(batch), accepted)
        sink.flush_strict()

        # Commit offsets only after the sink batch succeeded (at-least-once).
        if pending_offsets:
            try:
                consumer.commit(
                    offsets=[
                        TopicPartition(topic, partition, offset + 1)
                        for topic, partition, offset in pending_offsets
                    ],
                    asynchronous=False,
                )
            except Exception as exc:  # pragma: no cover - coordinator/runtime failure
                logger.warning("fan-out offset commit failed: %s", exc)
        last_flush = time.monotonic()

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    consumer = Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": group_id,
            "auto.offset.reset": auto_offset_reset,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    consumer.subscribe([input_topic])

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                flush()
                continue
            if message.error():
                logger.warning("fan-out consumer_error=%s", message.error())
                continue

            try:
                low, high = consumer.get_watermark_offsets(
                    TopicPartition(message.topic(), message.partition()), cached=True
                )
                if high >= 0:
                    set_consumer_lag(
                        "fanout",
                        message.topic(),
                        message.partition(),
                        high - (message.offset() + 1),
                    )
            except Exception:
                pass

            try:
                event = json.loads(message.value().decode("utf-8"))
            except Exception as exc:
                logger.warning("fan-out skipping unparseable record: %s", exc)
                continue

            buffer.append(event)
            offsets.append((message.topic(), message.partition(), message.offset()))
            flush()
            processed += 1

            if progress_every > 0 and processed % progress_every == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"fanout_processed={processed} rate={processed / elapsed:.1f}/sec")
    finally:
        flush(force=True)
        sink.close()
        consumer.close()


if __name__ == "__main__":
    main()
