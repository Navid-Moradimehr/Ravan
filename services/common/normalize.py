from __future__ import annotations

from typing import Any

from services.common.device_compat import tag_to_legacy_field


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_runtime_event(event: dict[str, Any]) -> dict[str, Any]:
    if "device_id" in event:
        return event

    tag = str(event.get("tag", ""))
    value = event.get("value", 0)
    timestamp = event.get("ts_source") or event.get("ts_ingest")

    normalized = {
        "event_id": event.get("event_id"),
        "device_id": event.get("asset_id", "unknown-asset"),
        "asset_id": event.get("asset_id", "unknown-asset"),
        "site_id": event.get("site", "demo-site"),
        "timestamp": timestamp,
        "source_protocol": event.get("source_protocol", "unknown"),
        "quality": event.get("quality", "unknown"),
        "schema_version": event.get("schema_version", 1),
        "temperature_c": 0.0,
        "vibration_mm_s": 0.0,
        "pressure_bar": 0.0,
        "tag": tag,
        "value": _to_float(value),
        "unit": event.get("unit", ""),
        "fault_type": event.get("fault_type", "normal"),
        "scenario_id": event.get("scenario_id", "sc-000"),
        "ground_truth_severity": event.get("ground_truth_severity", "normal"),
    }

    legacy_field = tag_to_legacy_field(tag)
    if legacy_field:
        normalized[legacy_field] = _to_float(value)

    return normalized


def to_legacy_iot_event(event: dict[str, Any] | Any) -> dict[str, Any]:
    event_dict = event.model_dump() if hasattr(event, "model_dump") else dict(event)

    tag = str(event_dict.get("tag", ""))
    value = event_dict.get("value", 0)

    base = {
        "event_id": event_dict.get("event_id"),
        "device_id": event_dict.get("asset_id", "unknown-asset"),
        "site_id": event_dict.get("site", "demo-site"),
        "timestamp": event_dict.get("ts_source"),
        "source_protocol": event_dict.get("source_protocol", "unknown"),
        "quality": event_dict.get("quality", "unknown"),
        "schema_version": event_dict.get("schema_version", 1),
        "temperature_c": 0.0,
        "vibration_mm_s": 0.0,
        "pressure_bar": 0.0,
    }

    legacy_field = tag_to_legacy_field(tag)
    if legacy_field:
        base[legacy_field] = _to_float(value)

    return base
