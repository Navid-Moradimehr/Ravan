"""Ingress for immutable non-scalar observation references.

The platform publishes references, not media bytes. The operator owns the
object store and its retention/authorization policy; Kafka carries the
versioned reference so downstream consumers can archive or process it.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException

from services.common.brokers import resolve_kafka_brokers
from services.common.model_data_contract import ObservationArtifactReference
from services.edge_ingest.model import to_json_bytes

router = APIRouter(tags=["observation-artifacts"])


@router.post("/api/v1/observation-artifacts")
async def ingest_observation_artifact(reference: ObservationArtifactReference) -> dict[str, Any]:
    """Publish one immutable artifact reference to the industrial artifact topic."""

    try:
        from confluent_kafka import Producer

        topic = os.getenv("INDUSTRIAL_ARTIFACT_TOPIC", "industrial.observation-artifacts")
        producer = Producer(
            {
                "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
                "client.id": "observation-artifact-ingest",
                "enable.idempotence": True,
                "acks": "all",
            }
        )
        producer.produce(
            topic,
            key=f"{reference.site_id}|{reference.entity_id}|{reference.artifact_id}".encode("utf-8"),
            value=to_json_bytes(reference),
        )
        remaining = producer.flush(10)
        if remaining:
            raise RuntimeError(f"artifact delivery incomplete: {remaining} messages pending")
        return {"status": "published", "topic": topic, "artifact_id": reference.artifact_id}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"observation artifact publish failed: {exc}") from exc
