"""Small shared helper for acknowledged Kafka dead-letter publication."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def publish_malformed_record(
    producer: Any,
    *,
    dlq_topic: str,
    source_topic: str,
    partition: int,
    offset: int,
    value: bytes,
    error: str,
) -> None:
    payload = {
        "source_protocol": "kafka",
        "source_id": f"{source_topic}:{partition}:{offset}",
        "error": error,
        "payload": value.decode("utf-8", errors="replace")[:16384],
        "metadata": {"source_topic": source_topic, "partition": partition, "offset": offset},
        "ts_ingest": datetime.now(timezone.utc).isoformat(),
        "schema_version": 1,
    }
    producer.produce(
        dlq_topic,
        key=f"{source_topic}:{partition}:{offset}".encode("utf-8"),
        value=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
    )
    if producer.flush(10):
        raise RuntimeError("dead-letter publication was not acknowledged")
