"""Per-source edge health state for Prometheus and local diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from prometheus_client import Gauge

source_state = Gauge("edge_source_state", "Current edge source state: 1 connected, 0 disconnected, -1 error", ["connection_id", "protocol", "site"])
source_last_success = Gauge("edge_source_last_success_epoch", "Last successful event epoch per edge source", ["connection_id", "protocol", "site"])
_lock = Lock()
_states: dict[str, dict[str, Any]] = {}
_history_path_raw = os.getenv("EDGE_SOURCE_HEALTH_HISTORY_PATH", "")
HISTORY_PATH = Path(_history_path_raw) if _history_path_raw else None
MAX_HISTORY = 5000


def _read_history() -> list[dict[str, Any]]:
    if HISTORY_PATH is None or not HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, ValueError):
        return []


def _record_transition(value: dict[str, Any]) -> None:
    if HISTORY_PATH is None:
        return
    records = (_read_history() + [dict(value)])[-MAX_HISTORY:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HISTORY_PATH.with_suffix(HISTORY_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(HISTORY_PATH)


def mark_source(connection_id: str, protocol: str, site: str, state: str, error: str = "") -> None:
    source_state.labels(connection_id=connection_id, protocol=protocol, site=site).set({"connected": 1.0, "disconnected": 0.0, "error": -1.0, "reconnecting": 0.0}.get(state, 0.0))
    value = {"connection_id": connection_id, "protocol": protocol, "site": site, "state": state, "error": error, "updated_at": datetime.now(timezone.utc).isoformat()}
    with _lock:
        previous = _states.get(connection_id)
        _states[connection_id] = value
        if previous is None or previous.get("state") != state or previous.get("error") != error:
            try:
                _record_transition(value)
            except OSError:
                pass


def mark_source_success(connection_id: str, protocol: str, site: str) -> None:
    source_last_success.labels(connection_id=connection_id, protocol=protocol, site=site).set(datetime.now(timezone.utc).timestamp())
    mark_source(connection_id, protocol, site, "connected")


def snapshot() -> list[dict[str, Any]]:
    with _lock:
        return [dict(value) for value in _states.values()]


def history(limit: int = 100) -> list[dict[str, Any]]:
    with _lock:
        records = _read_history()
    return records[-max(1, min(limit, MAX_HISTORY)):]
