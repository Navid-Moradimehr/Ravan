"""Small durable at-least-once delivery ledger for one-node federation.

The interface is intentionally storage-neutral so a PostgreSQL implementation
can replace this file for multi-replica deployments without changing callers.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DeliveryLedger:
    def __init__(self, path: str | Path | None = None, max_records: int | None = None) -> None:
        self.path = Path(path or os.getenv("FEDERATION_LEDGER_PATH", ".datastream/federation-ledger.json"))
        self.max_records = max(1, max_records or int(os.getenv("FEDERATION_LEDGER_MAX_RECORDS", "10000")))

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"records": {}}
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"records": {}}

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="federation-ledger-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, separators=(",", ":"))
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def claim(self, key: str) -> bool:
        state = self._read()
        records = state.setdefault("records", {})
        if key in records and records[key].get("status") == "succeeded":
            return False
        records[key] = {"status": "claimed", "updated_at": datetime.now(timezone.utc).isoformat()}
        self._prune(records)
        self._write(state)
        return True

    def record(self, key: str, *, status: str, metadata: dict[str, Any] | None = None) -> None:
        state = self._read()
        records = state.setdefault("records", {})
        entry = records.setdefault(key, {})
        entry.update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
        if metadata:
            entry["metadata"] = metadata
        self._prune(records)
        self._write(state)

    def snapshot(self, limit: int = 100) -> dict[str, Any]:
        records = self._read().get("records", {})
        items = list(records.items())[-max(1, limit):]
        return {"path": str(self.path), "count": len(records), "records": [{"key": key, **value} for key, value in items]}

    def _prune(self, records: dict[str, Any]) -> None:
        overflow = len(records) - self.max_records
        if overflow > 0:
            for key in list(records)[:overflow]:
                records.pop(key, None)
