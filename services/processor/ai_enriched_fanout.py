"""AI-enriched fan-out consumer.

Reads AI-enriched summary batches from ``iot.ai_enriched`` and persists them to
the historian ``ai_enriched`` table. The AI gateway only produces to Kafka; this
consumer owns historian persistence so the enrichment path is decoupled from the
endpoint dataset, matching the normalized fan-out pattern.

Offsets are committed only after a successful insert (at-least-once delivery).
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time

from confluent_kafka import Consumer, TopicPartition
from prometheus_client import start_http_server

from services.common.brokers import resolve_kafka_brokers
from services.common.runtime_metrics import set_consumer_lag
from services.historian.client import insert_ai_enriched

logger = logging.getLogger(__name__)


def main() -> None:
    start_http_server(int(os.getenv("AI_FANOUT_METRICS_PORT", "8096")))
    brokers = resolve_kafka_brokers("localhost:19092")
    input_topic = os.getenv("AI_ENRICHED_TOPIC", "iot.ai_enriched")
    group_id = os.getenv("AI_ENRICHED_FANOUT_GROUP_ID", "ai-enriched-fanout")
    progress_every = int(os.getenv("AI_ENRICHED_PROGRESS_EVERY", "1000"))
    # Default to latest so a container restart does not replay the entire topic.
    # Set AI_ENRICHED_AUTO_OFFSET_RESET=earliest for deliberate reprocessing.
    auto_offset_reset = os.getenv("AI_ENRICHED_AUTO_OFFSET_RESET", "latest")
    running = True

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

    processed = 0
    started_at = time.time()

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                logger.warning("ai-enriched fan-out consumer_error=%s", message.error())
                continue

            try:
                low, high = consumer.get_watermark_offsets(
                    TopicPartition(message.topic(), message.partition()), cached=True
                )
                if high >= 0:
                    set_consumer_lag(
                        "ai_enriched_fanout",
                        message.topic(),
                        message.partition(),
                        high - (message.offset() + 1),
                    )
            except Exception:
                pass

            try:
                event = json.loads(message.value().decode("utf-8"))
            except Exception as exc:
                logger.warning("ai-enriched fan-out skipping unparseable record: %s", exc)
                continue

            try:
                insert_ai_enriched(event)
            except Exception as exc:  # pragma: no cover - historian failure path
                logger.warning("ai-enriched insert failed: %s", exc)
                continue

            try:
                consumer.commit(
                    offsets=[
                        TopicPartition(
                            message.topic(), message.partition(), message.offset() + 1
                        )
                    ],
                    asynchronous=False,
                )
            except Exception as exc:  # pragma: no cover - coordinator failure
                logger.warning("ai-enriched fan-out offset commit failed: %s", exc)

            processed += 1
            if progress_every > 0 and processed % progress_every == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"ai_enriched_fanout_processed={processed} rate={processed / elapsed:.1f}/sec")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
