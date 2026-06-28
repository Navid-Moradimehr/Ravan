"""Real-time Data Preview — peek into Kafka topics without consuming offsets.

Uses Kafka consumer with a temporary group to show live samples.
"""
from __future__ import annotations

import json
import os
from typing import Any

from confluent_kafka import Consumer, KafkaError, TopicPartition


def peek_topic(topic: str, brokers: str = "localhost:19092", limit: int = 10, timeout: float = 5.0) -> list[dict[str, Any]]:
    """Peek into a Kafka topic without committing offsets."""
    conf = {
        "bootstrap.servers": brokers,
        "group.id": f"preview-{os.getpid()}",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    }
    consumer = Consumer(conf)
    try:
        # Get partitions
        metadata = consumer.list_topics(topic=topic)
        partitions = [
            TopicPartition(topic, p.id, offset=-1)  # -1 = latest
            for p in metadata.topics[topic].partitions.values()
        ]
        if not partitions:
            return []
        consumer.assign(partitions)
        # Seek to end minus limit per partition
        for tp in partitions:
            low, high = consumer.get_watermark_offsets(tp)
            start = max(low, high - limit)
            tp.offset = start
        consumer.assign(partitions)
        messages = []
        while len(messages) < limit:
            msg = consumer.poll(timeout=timeout)
            if msg is None:
                break
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                break
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"raw": msg.value().decode("utf-8", errors="replace")}
            messages.append({
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "timestamp": msg.timestamp()[1] if msg.timestamp() else None,
                "payload": payload,
            })
        return messages
    finally:
        consumer.close()


def list_topics(brokers: str = "localhost:19092") -> list[str]:
    """List available Kafka topics."""
    conf = {
        "bootstrap.servers": brokers,
        "group.id": f"preview-{os.getpid()}",
    }
    consumer = Consumer(conf)
    try:
        metadata = consumer.list_topics()
        return [t for t in metadata.topics.keys() if not t.startswith("__")]
    finally:
        consumer.close()
