"""Persist deterministic processed events without coupling Flink to TimescaleDB.

Flink owns the processing contract and publishes ``iot.processed``. This
consumer owns the historian projection, so the stream job remains restartable
and the historian can be retried independently.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time

from confluent_kafka import Consumer, Producer, TopicPartition
from prometheus_client import start_http_server

from services.common.brokers import resolve_kafka_brokers
from services.common.kafka_dlq import publish_malformed_record
from services.common.runtime_metrics import observe_fanout_write, set_consumer_lag
from services.historian.client import insert_processed_events

logger = logging.getLogger(__name__)


def main() -> None:
    start_http_server(int(os.getenv("PROCESSED_FANOUT_METRICS_PORT", "8097")))
    consumer = Consumer(
        {
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "group.id": os.getenv("PROCESSED_FANOUT_GROUP_ID", "processed-historian"),
            "auto.offset.reset": os.getenv("PROCESSED_FANOUT_AUTO_OFFSET_RESET", "latest"),
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    topic = os.getenv("PROCESSED_TOPIC", "iot.processed")
    batch_size = max(1, int(os.getenv("PROCESSED_FANOUT_BATCH_SIZE", "512")))
    flush_seconds = max(0.05, float(os.getenv("PROCESSED_FANOUT_FLUSH_SECONDS", "1")))
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    consumer.subscribe([topic])
    dlq_producer = Producer({"bootstrap.servers": resolve_kafka_brokers("localhost:19092"), "client.id": "processed-fanout-dlq"})
    dlq_topic = os.getenv("INDUSTRIAL_DLQ_TOPIC", "industrial.dlq")
    buffer: list[dict[str, object]] = []
    offsets: list[tuple[str, int, int]] = []
    last_flush = time.monotonic()

    def flush(force: bool = False) -> None:
        nonlocal last_flush
        if not buffer:
            return
        if not force and len(buffer) < batch_size and time.monotonic() - last_flush < flush_seconds:
            return
        batch = buffer[:]
        pending = offsets[:]
        write_started = time.monotonic()
        try:
            insert_processed_events(batch)
            observe_fanout_write(
                "processed_fanout", topic, len(batch), len(batch),
                time.monotonic() - write_started,
            )
            if pending:
                consumer.commit(
                    offsets=[
                        TopicPartition(topic_name, partition, offset + 1)
                        for topic_name, partition, offset in pending
                    ],
                    asynchronous=False,
                )
        except Exception:
            observe_fanout_write(
                "processed_fanout", topic, len(batch), 0,
                time.monotonic() - write_started, status="failed",
            )
            logger.exception("processed historian batch failed; offsets remain uncommitted")
            raise
        finally:
            buffer.clear()
            offsets.clear()
            last_flush = time.monotonic()

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                flush()
                continue
            if message.error():
                logger.warning("processed fan-out consumer error: %s", message.error())
                continue
            try:
                low, high = consumer.get_watermark_offsets(
                    TopicPartition(message.topic(), message.partition()), cached=True
                )
                if high >= 0:
                    set_consumer_lag("processed_fanout", message.topic(), message.partition(), high - message.offset() - 1)
            except Exception:
                logger.debug("processed fan-out lag probe failed", exc_info=True)
            try:
                event = json.loads(message.value().decode("utf-8"))
                if not isinstance(event, dict):
                    raise ValueError("processed event must be a JSON object")
            except Exception as exc:
                logger.exception("processed fan-out routing malformed event to DLQ")
                publish_malformed_record(
                    dlq_producer,
                    dlq_topic=dlq_topic,
                    source_topic=message.topic(),
                    partition=message.partition(),
                    offset=message.offset(),
                    value=message.value(),
                    error=f"processed fan-out decode failed: {exc}",
                )
                consumer.commit(
                    offsets=[TopicPartition(message.topic(), message.partition(), message.offset() + 1)],
                    asynchronous=False,
                )
                continue
            buffer.append(event)
            offsets.append((message.topic(), message.partition(), message.offset()))
            flush()
    finally:
        flush(force=True)
        dlq_producer.flush(10)
        consumer.close()


if __name__ == "__main__":
    main()
