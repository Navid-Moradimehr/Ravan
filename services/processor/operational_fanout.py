"""Optional operational-event archive consumer.

Operational events stay separate from the telemetry historian schema. When the
lakehouse sink is enabled, this consumer archives them as event-stage records;
Kafka remains the durable contract even when the optional archive is offline.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time

from confluent_kafka import Consumer

from services.common.brokers import resolve_kafka_brokers
from services.sinks.base import SinkRegistry

logger = logging.getLogger(__name__)


def main() -> None:
    topic = os.getenv("INDUSTRIAL_OPERATIONAL_TOPIC", "industrial.operational")
    group_id = os.getenv("OPERATIONAL_FANOUT_GROUP_ID", "operational-fanout")
    sink = SinkRegistry.from_env({**os.environ, "SINKS": os.getenv("OPERATIONAL_SINKS", "")})
    consumer = Consumer(
        {
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "group.id": group_id,
            "auto.offset.reset": os.getenv("OPERATIONAL_AUTO_OFFSET_RESET", "earliest"),
            "enable.auto.commit": False,
        }
    )
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer.subscribe([topic])
    buffer: list[dict[str, object]] = []
    offsets: list[tuple[str, int, int]] = []
    last_flush = time.monotonic()
    batch_size = max(1, int(os.getenv("OPERATIONAL_FANOUT_BATCH_SIZE", "512")))

    def flush(force: bool = False) -> None:
        nonlocal last_flush
        if not buffer or (not force and len(buffer) < batch_size and time.monotonic() - last_flush < 1):
            return
        batch = buffer[:]
        pending = offsets[:]
        buffer.clear()
        offsets.clear()
        sink.write_batch_strict(batch)
        sink.flush_strict()
        if pending:
            consumer.commit(asynchronous=False)
        last_flush = time.monotonic()

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                flush()
                continue
            if message.error():
                logger.warning("operational fanout consumer error: %s", message.error())
                continue
            try:
                event = json.loads(message.value().decode("utf-8"))
                event["event_stage"] = "operational"
                event["source_protocol"] = "operational"
                event["source_id"] = event.get("source_id", "unknown")
                event["asset_id"] = event.get("entity_id", "") or "operational-context"
                event["tag"] = event.get("event_type", "operational")
                event["site"] = event.get("site_id", "")
                event["ts_source"] = event.get("occurred_at", "")
                event["value"] = 0
                event["quality"] = "good"
                event["payload_json"] = json.dumps(event.get("payload", {}), sort_keys=True, default=str)
                buffer.append(event)
                offsets.append((message.topic(), message.partition(), message.offset()))
                flush()
            except Exception as exc:
                logger.warning("operational event archive failed: %s", exc)
    finally:
        flush(force=True)
        sink.close()
        consumer.close()


if __name__ == "__main__":
    main()
