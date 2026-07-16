"""Bounded, deployment-persistent source delivery history."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

PATH = Path(os.getenv("DATASTREAM_SOURCE_DELIVERY_HISTORY_PATH", ".datastream/source-delivery.json"))
MAX_RECORDS = 5000
_LOCK = Lock()


def record_delivery(*, connection_id: str, protocol: str, site: str, status: str, attempts: int = 1, error: str = "", records: int = 0) -> dict[str, Any]:
    record: dict[str, Any] = {
        "connection_id": connection_id,
        "protocol": protocol,
        "site": site,
        "status": status,
        "attempts": attempts,
        "records": records,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        record["error"] = str(error)[:500]
    with _LOCK:
        try:
            values: list[dict[str, Any]] = []
            if PATH.exists():
                payload = json.loads(PATH.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    values = payload
            values = (values + [record])[-MAX_RECORDS:]
            PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = PATH.with_suffix(PATH.suffix + ".tmp")
            temporary.write_text(json.dumps(values, indent=2, sort_keys=True), encoding="utf-8")
            temporary.replace(PATH)
        except (OSError, ValueError):
            pass
    return record


def recent(limit: int = 100) -> list[dict[str, Any]]:
    paths = [PATH]
    extra_path = os.getenv("DATASTREAM_EDGE_SOURCE_DELIVERY_HISTORY_PATH")
    if extra_path:
        paths.append(Path(extra_path))
    values: list[dict[str, Any]] = []
    with _LOCK:
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            except (OSError, ValueError):
                continue
            if isinstance(payload, list):
                values.extend(item for item in payload if isinstance(item, dict))
    values.sort(key=lambda item: str(item.get("updated_at", "")))
    return values[-max(1, min(limit, MAX_RECORDS)):][::-1]
