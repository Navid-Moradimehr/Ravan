"""Domain-neutral operational event contract and Kafka publisher."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from services.common.brokers import resolve_kafka_brokers
from services.edge_ingest.model import to_json_bytes


OperationalKind = Literal[
    "action",
    "outcome",
    "context",
    "boundary",
    "maintenance",
    "annotation",
]


class OperationalEvent(BaseModel):
    """Portable envelope for user-owned actions and operational context."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(min_length=1, max_length=160)
    event_kind: OperationalKind
    source_id: str = Field(min_length=1, max_length=256)
    site_id: str = Field(default="demo-site", min_length=1, max_length=256)
    entity_id: str = ""
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str = ""
    causation_id: str = ""
    schema_version: int = Field(default=1, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)


def publish_operational_event(event: OperationalEvent) -> dict[str, Any]:
    """Publish one event to Kafka; deployment owns the broker and topic policy."""
    from confluent_kafka import Producer

    topic = os.getenv("INDUSTRIAL_OPERATIONAL_TOPIC", "industrial.operational")
    producer = Producer(
        {
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "client.id": "operational-event-ingest",
            "enable.idempotence": True,
            "acks": "all",
        }
    )
    producer.produce(
        topic,
        key=f"{event.site_id}|{event.entity_id}|{event.event_type}".encode("utf-8"),
        value=to_json_bytes(event),
    )
    remaining = producer.flush(10)
    if remaining:
        raise RuntimeError(f"operational event delivery incomplete: {remaining} messages pending")
    return {"status": "published", "topic": topic, "event_id": event.event_id}
