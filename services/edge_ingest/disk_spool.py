"""Small crash-tolerant JSONL spool for edge events that cannot reach Kafka."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any


class DiskEventSpool:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.pending_path = self.directory / "pending.ndjson"

    def append(self, topic: str, key: bytes, value: bytes) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.pending_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"topic": topic, "key": base64.b64encode(key).decode("ascii"), "value": base64.b64encode(value).decode("ascii")}, separators=(",", ":")) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.pending_path.exists():
            return []
        return [json.loads(line) for line in self.pending_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def count(self) -> int:
        if not self.pending_path.exists():
            return 0
        return sum(1 for line in self.pending_path.read_text(encoding="utf-8").splitlines() if line.strip())

    def replace(self, records: list[dict[str, Any]]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if not records:
            self.pending_path.unlink(missing_ok=True)
            return
        temporary = self.pending_path.with_suffix(".tmp")
        temporary.write_text("".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records), encoding="utf-8")
        temporary.replace(self.pending_path)

    @staticmethod
    def decode(record: dict[str, Any]) -> tuple[str, bytes, bytes]:
        return record["topic"], base64.b64decode(record["key"]), base64.b64decode(record["value"])
