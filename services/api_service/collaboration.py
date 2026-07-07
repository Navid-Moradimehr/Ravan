"""Collaboration features — annotations, comments, shared dashboards.

Open-source: inspired by Grafana annotations and GitHub discussions.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Annotation:
    annotation_id: str
    target_type: str  # event, alarm, trend, dashboard
    target_id: str
    user_id: str
    username: str
    text: str
    timestamp: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "user_id": self.user_id,
            "username": self.username,
            "text": self.text,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


class CollaborationStore:
    """In-memory store for annotations and comments."""

    def __init__(self, state_path: str | os.PathLike[str] | None = None):
        self._state_path = Path(state_path) if state_path else None
        self._annotations: list[Annotation] = []
        if self._state_path and self._state_path.exists():
            self._load_state()

    def add_annotation(self, target_type: str, target_id: str, user_id: str, username: str, text: str, tags: list[str] | None = None) -> Annotation:
        ann = Annotation(
            annotation_id=f"ann-{uuid.uuid4().hex[:8]}",
            target_type=target_type,
            target_id=target_id,
            user_id=user_id,
            username=username,
            text=text,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
        )
        self._annotations.append(ann)
        self._persist_state()
        return ann

    def list_annotations(self, target_type: str | None = None, target_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        results = self._annotations
        if target_type:
            results = [a for a in results if a.target_type == target_type]
        if target_id:
            results = [a for a in results if a.target_id == target_id]
        results.sort(key=lambda a: a.timestamp, reverse=True)
        return [a.to_dict() for a in results[:limit]]

    def delete_annotation(self, annotation_id: str) -> bool:
        for i, a in enumerate(self._annotations):
            if a.annotation_id == annotation_id:
                self._annotations.pop(i)
                self._persist_state()
                return True
        return False

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive bootstrap path
            raise ValueError(f"failed to load collaboration store state from {self._state_path}") from exc
        self._annotations = [
            Annotation(
                annotation_id=item["annotation_id"],
                target_type=item["target_type"],
                target_id=item["target_id"],
                user_id=item["user_id"],
                username=item["username"],
                text=item["text"],
                timestamp=item.get("timestamp", ""),
                tags=list(item.get("tags", [])),
            )
            for item in payload.get("annotations", [])
        ]

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps({"annotations": [a.to_dict() for a in self._annotations]}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self._state_path)


# Global store
COLLABORATION_STORE_PATH = os.environ.get("COLLABORATION_STORE_PATH")
collaboration_store = CollaborationStore(state_path=COLLABORATION_STORE_PATH)
