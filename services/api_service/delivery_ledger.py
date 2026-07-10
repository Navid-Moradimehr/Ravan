"""Small durable notification delivery ledger.

This is an operator-facing status record, not a guaranteed message queue. It
is intentionally bounded so notification delivery cannot grow the API data
volume without limit. Provider credentials and full destination URLs are not
stored.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_RECORDS = 1000
LEDGER_PATH = Path(os.getenv("DATASTREAM_DELIVERY_LEDGER_PATH", ".datastream/delivery-ledger.json"))


def _load() -> list[dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return []
    try:
        payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except (OSError, ValueError):
        return []


def _persist(records: list[dict[str, Any]]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = LEDGER_PATH.with_suffix(LEDGER_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(records[-MAX_RECORDS:], indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(LEDGER_PATH)


def safe_destination(value: str) -> str:
    """Return a non-secret destination label for operator diagnostics."""
    try:
        parsed = urlparse(value)
        return "://".join(part for part in (parsed.scheme, parsed.hostname or "") if part) or "configured-channel"
    except Exception:
        return "configured-channel"


def record_delivery(*, channel: str, kind: str, ok: bool, attempts: int = 1, status: int = 0, error: str | None = None) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": safe_destination(channel),
        "kind": kind,
        "status": "delivered" if ok else "failed",
        "attempts": attempts,
        "http_status": status or None,
    }
    if error:
        record["error"] = str(error)[:500]
    records = _load()
    records.append(record)
    try:
        _persist(records)
    except OSError:
        # Delivery status must never make an otherwise successful delivery fail.
        pass
    return record


def recent_deliveries(limit: int = 50) -> list[dict[str, Any]]:
    return _load()[-max(1, min(limit, MAX_RECORDS)):]
