"""Collaboration features — annotations, comments, shared dashboards.

Open-source: inspired by Grafana annotations and GitHub discussions.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

    def __init__(self):
        self._annotations: list[Annotation] = []

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
                return True
        return False


# Global store
collaboration_store = CollaborationStore()
