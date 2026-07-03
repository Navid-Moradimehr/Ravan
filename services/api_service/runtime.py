from __future__ import annotations

import json
import os
from typing import Any
from functools import lru_cache

import httpx

from services.common.stream_scope import stream_partition_key

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
        from services.historian.client import insert_industrial_event, insert_dead_letter  # type: ignore
    except Exception:
        from historian.client import insert_industrial_event, insert_dead_letter  # type: ignore

    brokers = os.getenv("REDPANDA_BROKERS", "localhost:19092")
    normalized_topic = os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized")
    raw_topic = os.getenv("INDUSTRIAL_RAW_TOPIC", "industrial.raw")
    legacy_topic = os.getenv("IOT_TOPIC", "iot.raw")
    dlq_topic = os.getenv("INDUSTRIAL_DLQ_TOPIC", "industrial.dlq")

    payload = {
        "event_id": str(_uuid.uuid4()),
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
    }

    event_model, dlq = validate_event(payload)
    event_id = str(_uuid.uuid4())
    if dlq is not None:
        try:
            _publish_kafka_fresh(brokers, dlq_topic, str(payload.get("source_id", "api")).encode(), to_json_bytes(dlq))
        except Exception:
            pass
        try:
            insert_dead_letter({**dlq.model_dump(mode="json"), "origin": "api"})
        except Exception:
            pass
        return {"status": "rejected", "event_id": dlq.event_id, "reason": "validation_failed"}

    event_dict = event_model.model_dump(mode="json")
    try:
        insert_industrial_event(event_dict)
    except Exception:
        pass

    key = stream_partition_key(event_dict)
    try:
        legacy_event = _to_legacy_iot_event(event_dict)
        _publish_kafka(brokers, raw_topic, key, to_json_bytes(event_dict))
        _publish_kafka(brokers, normalized_topic, key, to_json_bytes(event_dict))
        _publish_kafka(brokers, legacy_topic, key, to_json_bytes(legacy_event))
    except Exception as e:
        return {"status": "stored_only", "event_id": event_id, "warning": f"kafka_publish_failed: {e}"}
    return {"status": "ingested", "event_id": event_id}


def _publish_kafka(brokers: str, topic: str, key: bytes, value: bytes) -> None:
    producer = _get_producer(brokers)
    producer.produce(topic, key=key, value=value)
    producer.flush(5)


def _publish_kafka_fresh(brokers: str, topic: str, key: bytes, value: bytes) -> None:
    from confluent_kafka import Producer

    producer = Producer({"bootstrap.servers": brokers, "client.id": "api-ingest"})
    producer.produce(topic, key=key, value=value)
    producer.flush(5)


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
