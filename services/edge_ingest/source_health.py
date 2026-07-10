"""Per-source edge health state for Prometheus and local diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any

from prometheus_client import Gauge

source_state = Gauge("edge_source_state", "Current edge source state: 1 connected, 0 disconnected, -1 error", ["connection_id", "protocol", "site"])
source_last_success = Gauge("edge_source_last_success_epoch", "Last successful event epoch per edge source", ["connection_id", "protocol", "site"])
_lock = Lock()
_states: dict[str, dict[str, Any]] = {}


def mark_source(connection_id: str, protocol: str, site: str, state: str, error: str = "") -> None:
    source_state.labels(connection_id=connection_id, protocol=protocol, site=site).set({"connected": 1.0, "disconnected": 0.0, "error": -1.0, "reconnecting": 0.0}.get(state, 0.0))
    with _lock:
        _states[connection_id] = {"connection_id": connection_id, "protocol": protocol, "site": site, "state": state, "error": error, "updated_at": datetime.now(timezone.utc).isoformat()}


def mark_source_success(connection_id: str, protocol: str, site: str) -> None:
    source_last_success.labels(connection_id=connection_id, protocol=protocol, site=site).set(datetime.now(timezone.utc).timestamp())
    mark_source(connection_id, protocol, site, "connected")


def snapshot() -> list[dict[str, Any]]:
    with _lock:
        return [dict(value) for value in _states.values()]
