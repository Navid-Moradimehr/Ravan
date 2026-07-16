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

from confluent_kafka import Consumer, Producer, TopicPartition

from services.common.brokers import resolve_kafka_brokers
from services.common.kafka_dlq import publish_malformed_record
from services.sinks.base import SinkRegistry

logger = logging.getLogger(__name__)


def main() -> None:
    topic = os.getenv("INDUSTRIAL_OPERATIONAL_TOPIC", "industrial.operational")
    group_id = os.getenv("OPERATIONAL_FANOUT_GROUP_ID", "operational-fanout")
    sink = SinkRegistry.from_env({
        **os.environ,
        "SINKS": os.getenv("OPERATIONAL_SINKS", ""),
        "LAKEHOUSE_EVENT_FAMILY": "operational",
    })
    consumer = Consumer(
        {
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "group.id": group_id,
            "auto.offset.reset": os.getenv("OPERATIONAL_AUTO_OFFSET_RESET", "earliest"),
            "enable.auto.commit": False,
        }
    )
    dlq_producer = Producer({"bootstrap.servers": resolve_kafka_brokers("localhost:19092"), "client.id": "operational-fanout-dlq"})
    dlq_topic = os.getenv("INDUSTRIAL_DLQ_TOPIC", "industrial.dlq")
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
        sink.write_batch_strict(batch)
        sink.flush_strict()
        if pending:
            consumer.commit(
                offsets=[TopicPartition(topic_name, partition, offset + 1) for topic_name, partition, offset in pending],
                asynchronous=False,
            )
        del buffer[:len(batch)]
        del offsets[:len(pending)]
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
            except Exception as exc:
                flush(force=True)
                logger.warning("operational fanout routing malformed record to DLQ: %s", exc)
                publish_malformed_record(
                    dlq_producer, dlq_topic=dlq_topic, source_topic=message.topic(),
                    partition=message.partition(), offset=message.offset(), value=message.value(),
                    error=f"operational fanout decode failed: {exc}",
                )
                consumer.commit(message=message, asynchronous=False)
                continue
            if not isinstance(event, dict):
                flush(force=True)
                publish_malformed_record(
                    dlq_producer, dlq_topic=dlq_topic, source_topic=message.topic(),
                    partition=message.partition(), offset=message.offset(), value=message.value(),
                    error="operational event must be a JSON object",
                )
                consumer.commit(message=message, asynchronous=False)
                continue
            event["event_stage"] = "operational"
            buffer.append(event)
            offsets.append((message.topic(), message.partition(), message.offset()))
            flush()
    finally:
        flush(force=True)
        dlq_producer.flush(10)
        sink.close()
        consumer.close()


if __name__ == "__main__":
    main()
