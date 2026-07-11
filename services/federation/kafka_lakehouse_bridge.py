"""Optional central consumer for federated Kafka topics.

Run this in the central environment. Site-local installations do not import
or depend on this process.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import json as json_module
from pathlib import Path
import time

from confluent_kafka import Consumer, TopicPartition

from services.common.brokers import resolve_kafka_brokers
from services.common.runtime_metrics import set_federation_lag
from services.federation.policy import allowed_topics, topic_allowed
from services.sinks.lakehouse import LakehouseSink

logger = logging.getLogger(__name__)


def main() -> None:
    topic = os.getenv("FEDERATION_INPUT_TOPIC", "local.industrial.normalized")
    allowed = allowed_topics(os.getenv("DATASTREAM_PROJECT_MANIFEST", ""), os.getenv("FEDERATION_ALLOWED_TOPICS", ""))
    original_topic = topic.split(".", 1)[1] if topic.startswith("local.") else topic
    if os.getenv("FEDERATION_ENFORCE_TOPIC_POLICY", "true").lower() in {"1", "true", "yes", "on"} and not topic_allowed(original_topic, allowed):
        raise SystemExit(f"federation topic is not approved: {original_topic}")
    sink = LakehouseSink.from_env({**os.environ, "SINKS": "lakehouse"})
    consumer = Consumer(
        {
            "bootstrap.servers": resolve_kafka_brokers(os.getenv("CENTRAL_KAFKA_BROKERS", "localhost:9092")),
            "group.id": os.getenv("FEDERATION_LAKEHOUSE_GROUP_ID", "central-lakehouse-writer"),
            "auto.offset.reset": os.getenv("FEDERATION_AUTO_OFFSET_RESET", "earliest"),
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
    batch: list[dict[str, object]] = []
    batch_size = max(1, int(os.getenv("FEDERATION_LAKEHOUSE_BATCH_SIZE", "512")))

    def flush() -> None:
        if not batch:
            return
        sink.write_batch_strict(batch[:])
        sink.flush_strict()
        batch.clear()
        consumer.commit(asynchronous=False)

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                flush()
                continue
            if message.error():
                logger.warning("central federation consumer error: %s", message.error())
                continue
            try:
                _, high = consumer.get_watermark_offsets(TopicPartition(message.topic(), message.partition()))
                set_federation_lag(message.topic(), max(high - message.offset() - 1, 0))
            except Exception:
                pass
            try:
                event = json.loads(message.value().decode("utf-8"))
                event["federation_source_topic"] = message.topic()
                batch.append(event)
                if len(batch) >= batch_size:
                    flush()
                status_path = os.getenv("FEDERATION_STATUS_PATH", "")
                if status_path:
                    Path(status_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(status_path).write_text(
                        json_module.dumps({"status": "healthy", "topic": message.topic(), "last_message_at": time.time()}),
                        encoding="utf-8",
                    )
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
                logger.warning("central federation skipped invalid event: %s", exc)
    finally:
        flush()
        sink.close()
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
