"""Optional Kafka-to-lakehouse archive for immutable artifact references."""

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
    topic = os.getenv("INDUSTRIAL_ARTIFACT_TOPIC", "industrial.observation-artifacts")
    group_id = os.getenv("ARTIFACT_FANOUT_GROUP_ID", "artifact-fanout")
    sink = SinkRegistry.from_env(
        {
            **os.environ,
            "SINKS": os.getenv("ARTIFACT_SINKS", "lakehouse"),
            "LAKEHOUSE_EVENT_FAMILY": "artifact",
        }
    )
    consumer = Consumer(
        {
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "group.id": group_id,
            "auto.offset.reset": os.getenv("ARTIFACT_AUTO_OFFSET_RESET", "earliest"),
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
    batch_size = max(1, int(os.getenv("ARTIFACT_FANOUT_BATCH_SIZE", "256")))
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
                logger.warning("artifact fanout consumer error: %s", message.error())
                continue
            try:
                event = json.loads(message.value().decode("utf-8"))
                if not isinstance(event, dict):
                    raise ValueError("artifact record must be a JSON object")
                event["event_stage"] = "artifact-reference"
                buffer.append(event)
                flush()
            except Exception as exc:
                logger.warning("artifact archive failed: %s", exc)
    finally:
        flush(force=True)
        sink.close()
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
