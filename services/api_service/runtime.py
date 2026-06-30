from __future__ import annotations

import json
import os
from typing import Any

import httpx

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
    if dlq is not None:
        insert_dead_letter(dlq.model_dump(mode="json"))
        return {"status": "rejected", "event_id": dlq.event_id}

    insert_industrial_event(event_model.model_dump(mode="json"))
    return {"status": "received", "event_id": event_model.event_id}
