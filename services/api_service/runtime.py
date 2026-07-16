from __future__ import annotations

import json
import os
from typing import Any
from functools import lru_cache

import httpx

from services.common.brokers import resolve_kafka_brokers
from services.common.stream_scope import stream_partition_key
from services.common.native_fastpath import encode_event_bundle

try:
    from assets.model import load_hierarchy, hierarchy_to_tree
except ImportError:
    from services.assets.model import load_hierarchy, hierarchy_to_tree  # type: ignore
try:
    from scenarios.engine import list_scenarios
except ImportError:
    from services.scenarios.engine import list_scenarios  # type: ignore


def build_asset_hierarchy() -> list[dict[str, Any]]:
    config_path = os.getenv("ASSETS_CONFIG_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "config", "assets.yaml"))
    try:
        return hierarchy_to_tree(load_hierarchy(config_path))
    except Exception:
        return []


def _do_ingest_event(event: dict[str, Any]) -> dict[str, str]:
    import uuid as _uuid

    try:
        from services.edge_ingest.model import validate_event, to_json_bytes, utc_now  # type: ignore
    except Exception:
        from edge_ingest.model import validate_event, to_json_bytes, utc_now  # type: ignore
    try:
        from services.historian.client import insert_dead_letter  # type: ignore
    except Exception:
        from historian.client import insert_dead_letter  # type: ignore

    brokers = resolve_kafka_brokers("localhost:19092")
    normalized_topic = os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized")
    raw_topic = os.getenv("INDUSTRIAL_RAW_TOPIC", "industrial.raw")
    legacy_topic = os.getenv("IOT_TOPIC", "iot.raw")
    dlq_topic = os.getenv("INDUSTRIAL_DLQ_TOPIC", "industrial.dlq")

    payload = {
        "event_id": str(event.get("event_id") or _uuid.uuid4()),
        "source_protocol": event.get("source_protocol", "api"),
        "source_id": event.get("source_id", ""),
        "asset_id": event.get("asset_id", ""),
        "tag": event.get("tag", ""),
        "value": event.get("value", 0),
        "quality": event.get("quality", "good"),
        "unit": event.get("unit", ""),
        "site": event.get("site", "demo-site"),
        "line": event.get("line", "line-01"),
        "ts_source": event.get("ts_source") or utc_now(),
        "source_connection_id": event.get("source_connection_id", ""),
        "source_config_version": event.get("source_config_version", 0),
        "mapping_version": event.get("mapping_version", ""),
        "lineage_id": event.get("lineage_id", ""),
    }

    event_model, dlq = validate_event(payload)
    if dlq is not None:
        try:
            _publish_kafka(brokers, dlq_topic, str(payload.get("source_id", "api")).encode(), to_json_bytes(dlq))
        except Exception:
            pass
        try:
            insert_dead_letter({**dlq.model_dump(mode="json"), "origin": "api"})
        except Exception:
            pass
        try:
            from services.common.semantic_store import SemanticLineageRecord, get_semantic_store

            get_semantic_store().record_lineage(
                SemanticLineageRecord(
                    lineage_id=str(_uuid.uuid4()),
                    kind="rejected_event",
                    source_id=str(payload.get("source_id", "api")),
                    entity_id=str(payload.get("asset_id", "")),
                    site_id=str(payload.get("site", "demo-site")),
                    occurred_at=payload.get("ts_source", ""),
                    metadata={"reason": "validation_failed", "event_id": dlq.event_id},
                )
            )
        except Exception:
            pass
        return {"status": "rejected", "event_id": dlq.event_id, "reason": "validation_failed"}

    event_dict = event_model.model_dump(mode="json")
    # Historian persistence is owned by the normalized fan-out consumer, which
    # reads industrial.normalized and writes via the sink layer. The API only
    # validates and publishes; it no longer dual-writes to the historian.
    bundle = encode_event_bundle(event_dict)
    if bundle is None:
        key = stream_partition_key(event_dict)
        normalized_bytes = to_json_bytes(event_dict)
        legacy_event = _to_legacy_iot_event(event_dict)
        legacy_bytes = to_json_bytes(legacy_event)
    else:
        key, normalized_bytes, legacy_bytes = bundle
    try:
        _publish_kafka_batch(
            brokers,
            (
                (raw_topic, to_json_bytes(event_dict)),
                (normalized_topic, normalized_bytes),
                (legacy_topic, legacy_bytes),
            ),
            key,
        )
    except Exception as e:
        return {
            "status": "publish_failed",
            "event_id": str(event_dict.get("event_id", payload["event_id"])),
            "warning": f"kafka_publish_failed: {e}",
        }
    try:
        from services.common.semantic_store import SemanticLineageRecord, get_semantic_store

        get_semantic_store().record_lineage(
            SemanticLineageRecord(
                lineage_id=str(_uuid.uuid4()),
                kind="ingested_event",
                source_id=str(event_dict.get("source_id", payload.get("source_id", "api"))),
                target_id=str(event_dict.get("event_id", "")),
                entity_id=str(event_dict.get("asset_id", "")),
                site_id=str(event_dict.get("site", "demo-site")),
                occurred_at=str(event_dict.get("ts_source", "")),
                metadata={
                    "source_protocol": event_dict.get("source_protocol", ""),
                    "tag": event_dict.get("tag", ""),
                    "quality": event_dict.get("quality", ""),
                },
            )
        )
    except Exception:
        pass
    return {"status": "ingested", "event_id": str(event_dict.get("event_id", payload["event_id"]))}


def _publish_kafka(brokers: str, topic: str, key: bytes, value: bytes) -> None:
    producer = _get_producer(brokers)
    producer.produce(topic, key=key, value=value)
    if producer.flush(5):
        raise RuntimeError(f"Kafka delivery timed out for topic {topic}")


def _publish_kafka_batch(
    brokers: str,
    records: tuple[tuple[str, bytes], ...],
    key: bytes,
) -> None:
    producer = _get_producer(brokers)
    for topic, value in records:
        producer.produce(topic, key=key, value=value)
    if producer.flush(5):
        raise RuntimeError("Kafka delivery timed out for ingest event bundle")


@lru_cache(maxsize=4)
def _get_producer(brokers: str):
    from confluent_kafka import Producer

    return Producer({"bootstrap.servers": brokers, "client.id": "api-ingest"})


def _to_legacy_iot_event(event: Any) -> dict[str, Any]:
    try:
        from common.normalize import to_legacy_iot_event

        return to_legacy_iot_event(event)
    except Exception:
        data = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        return {
            "event_id": data.get("event_id"),
            "device_id": data.get("asset_id", "unknown-asset"),
            "site_id": data.get("site", "demo-site"),
            "timestamp": data.get("ts_source"),
            "source_protocol": data.get("source_protocol", "unknown"),
            "quality": data.get("quality", "unknown"),
            "schema_version": data.get("schema_version", 1),
            "temperature_c": 0.0,
            "vibration_mm_s": 0.0,
            "pressure_bar": 0.0,
        }
