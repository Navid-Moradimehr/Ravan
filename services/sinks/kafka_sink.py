"""Kafka sink.

Forwards normalized events to a downstream Kafka topic. Useful when a consumer
wants the normalized stream delivered to a separate cluster/topic for replay,
analytics, or a lakehouse ingestion job, decoupled from the processor.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from services.common.brokers import resolve_kafka_brokers
from services.common.stream_scope import stream_partition_key
from services.edge_ingest.model import to_json_bytes

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Producer

    _KAFKA_AVAILABLE = True
except ImportError:  # pragma: no cover - environments without confluent_kafka
    Producer = None  # type: ignore[assignment]
    _KAFKA_AVAILABLE = False


class KafkaSink:
    """Forward normalized events to a downstream Kafka topic.

    The composite key (site|line|protocol|source|asset|tag) is reused so
    partitioning stays consistent with the rest of the platform.
    """

    name = "kafka"

    def __init__(self, brokers: str, topic: str, batch_size: int = 512) -> None:
        if not _KAFKA_AVAILABLE:
            raise RuntimeError("confluent_kafka is required for the KafkaSink")
        self._brokers = brokers
        self._topic = topic
        self._batch_size = batch_size
        self._producer = Producer(
            {
                "bootstrap.servers": brokers,
                "client.id": "sink-kafka",
                "enable.idempotence": True,
                "acks": "all",
                "linger.ms": 10,
                "compression.type": "lz4",
            }
        )
        self._pending = 0

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "KafkaSink":
        brokers = resolve_kafka_brokers("localhost:19092")
        topic = env.get("KAFKA_SINK_TOPIC", "industrial.fanout")
        batch_size = int(env.get("KAFKA_SINK_BATCH_SIZE", "512"))
        return cls(brokers=brokers, topic=topic, batch_size=batch_size)

    def write_batch(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0
        for event in events:
            key = stream_partition_key(event)
            self._producer.produce(self._topic, key=key, value=to_json_bytes(event))
            self._pending += 1
            if self._pending >= self._batch_size:
                self._producer.poll(0)
                self._pending = 0
        return len(events)

    def flush(self) -> None:
        self._producer.poll(0)

    def close(self) -> None:
        self._producer.flush(10)
