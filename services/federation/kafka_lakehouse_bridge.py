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
from services.common.federation_contract import FederationContractError, deduplication_key, unwrap_event
from services.common.runtime_metrics import observe_federation_delivery, set_federation_lag
from services.federation.delivery_ledger import DeliveryLedger
from services.federation.policy import allowed_topics, topic_allowed
from services.sinks.lakehouse import LakehouseSink

logger = logging.getLogger(__name__)


def decode_forwarded_message(raw: bytes, *, topic: str, allow_legacy: bool = True) -> tuple[dict[str, object], dict[str, object], str]:
    """Decode and validate one broker record before it reaches a sink."""
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise FederationContractError("forwarded event must be a JSON object")
    event, metadata = unwrap_event(value, allow_legacy=allow_legacy)
    key = deduplication_key(value, topic=topic)
    event = dict(event)
    event["federation_source_topic"] = topic
    if metadata.get("legacy"):
        event["federation_legacy"] = True
    else:
        event["federation_origin"] = metadata
    return event, metadata, key


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
    batch_keys: list[str] = []
    batch_size = max(1, int(os.getenv("FEDERATION_LAKEHOUSE_BATCH_SIZE", "512")))
    ledger = DeliveryLedger()
    duplicate_count = 0
    invalid_count = 0

    def flush() -> None:
        if not batch:
            return
        try:
            sink.write_batch_strict(batch[:])
            sink.flush_strict()
        except Exception as exc:
            for key in batch_keys:
                ledger.record(key, status="failed", metadata={"error": str(exc)[:500]})
            observe_federation_delivery(topic, "sink_failed", len(batch_keys))
            raise
        for key in batch_keys:
            ledger.record(key, status="succeeded")
        observe_federation_delivery(topic, "sink_succeeded", len(batch_keys))
        batch.clear()
        batch_keys.clear()
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
                event, metadata, key = decode_forwarded_message(
                    message.value(), topic=message.topic(), allow_legacy=os.getenv("FEDERATION_ALLOW_LEGACY", "true").lower() in {"1", "true", "yes", "on"}
                )
                if not ledger.claim(key):
                    duplicate_count += 1
                    observe_federation_delivery(message.topic(), "duplicate")
                    logger.info("central federation skipped duplicate event key=%s", key)
                    consumer.commit(asynchronous=False)
                    continue
                ledger.record(key, status="claimed", metadata=metadata)
                batch.append(event)
                batch_keys.append(key)
                if len(batch) >= batch_size:
                    flush()
                status_path = os.getenv("FEDERATION_STATUS_PATH", "")
                if status_path:
                    Path(status_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(status_path).write_text(
                        json_module.dumps({
                            "status": "healthy",
                            "topic": message.topic(),
                            "last_message_at": time.time(),
                            "duplicates": duplicate_count,
                            "invalid": invalid_count,
                            "last_origin": metadata,
                        }),
                        encoding="utf-8",
                    )
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, FederationContractError) as exc:
                invalid_count += 1
                observe_federation_delivery(message.topic(), "invalid")
                logger.warning("central federation skipped invalid event: %s", exc)
    finally:
        flush()
        sink.close()
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
