"""Optional immutable raw-topic archive.

This consumer is intentionally separate from normalized fan-out. It is
disabled unless an operator starts the corresponding Compose profile and
should be used only when raw payload retention has been approved.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time

from confluent_kafka import Consumer

from services.common.brokers import resolve_kafka_brokers
from services.sinks.lakehouse import LakehouseSink

logger = logging.getLogger(__name__)


def main() -> None:
    topic = os.getenv("INDUSTRIAL_RAW_TOPIC", "industrial.raw")
    group_id = os.getenv("RAW_ARCHIVE_GROUP_ID", "raw-lakehouse-archive")
    batch_size = max(1, int(os.getenv("RAW_ARCHIVE_BATCH_SIZE", "512")))
    env = {
        **os.environ,
        "LAKEHOUSE_TABLE": os.getenv("LAKEHOUSE_RAW_TABLE", "raw_events"),
        "LAKEHOUSE_TABLE_TEMPLATE": os.getenv("LAKEHOUSE_RAW_TABLE_TEMPLATE", "raw_events"),
    }
    sink = LakehouseSink.from_env(env)
    consumer = Consumer(
        {
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "group.id": group_id,
            "auto.offset.reset": os.getenv("RAW_ARCHIVE_AUTO_OFFSET_RESET", "earliest"),
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
    last_flush = time.monotonic()

    def flush(force: bool = False) -> None:
        nonlocal last_flush
        if not buffer or (not force and len(buffer) < batch_size and time.monotonic() - last_flush < 1):
            return
        batch = buffer[:]
        buffer.clear()
        sink.write_batch_strict(batch)
        sink.flush_strict()
        consumer.commit(asynchronous=False)
        last_flush = time.monotonic()

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                flush()
                continue
            if message.error():
                logger.warning("raw archive consumer error: %s", message.error())
                continue
            try:
                event = json.loads(message.value().decode("utf-8"))
                event["event_stage"] = "raw"
                event["payload_json"] = json.dumps(event, sort_keys=True, default=str)
                event.setdefault("site", event.get("site_id", ""))
                event.setdefault("ts_ingest", event.get("ts_source", ""))
                buffer.append(event)
                flush()
            except Exception as exc:
                logger.warning("raw archive skipped invalid record: %s", exc)
    finally:
        flush(force=True)
        sink.close()
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
