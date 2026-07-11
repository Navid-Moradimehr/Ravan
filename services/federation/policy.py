"""Small, reusable federation policy helpers."""

from __future__ import annotations

from pathlib import Path

from services.common.project_manifest import load_project_manifest


DEFAULT_FEDERATION_TOPICS = ("industrial.normalized", "industrial.operational")


def allowed_topics(manifest_path: str | Path | None = None, configured: str = "") -> frozenset[str]:
    if configured.strip():
        return frozenset(item.strip() for item in configured.split(",") if item.strip())
    if manifest_path and Path(manifest_path).exists():
        return frozenset(load_project_manifest(manifest_path).federation.topics)
    return frozenset(DEFAULT_FEDERATION_TOPICS)


def topic_allowed(topic: str, topics: frozenset[str]) -> bool:
    return topic in topics
