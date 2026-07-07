from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.common.ai_event_contract import AI_EVENT_CONTRACTS
from services.common.project_manifest import load_project_manifest


@dataclass(frozen=True)
class EventCatalogEntry:
    topic: str
    stage: str
    description: str
    category: str = "industrial"
    owner: str = "platform"
    producers: tuple[str, ...] = field(default_factory=tuple)
    consumers: tuple[str, ...] = field(default_factory=tuple)
    site_scoped: bool = False
    retained: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CANONICAL_EVENT_TOPICS: tuple[EventCatalogEntry, ...] = (
    EventCatalogEntry(
        topic="industrial.raw",
        stage="raw",
        description="Unvalidated industrial envelopes from edge adapters.",
        category="industrial",
        producers=("edge.ingest", "rest.ingest"),
        consumers=("validation", "normalization"),
        site_scoped=True,
        retained=False,
    ),
    EventCatalogEntry(
        topic="industrial.normalized",
        stage="normalized",
        description="Validated canonical industrial events ready for fan-out and processing.",
        category="industrial",
        producers=("validation", "normalization"),
        consumers=("historian.sink", "runtime.processor", "flink.job", "semantic.lineage"),
        site_scoped=True,
        retained=True,
    ),
    EventCatalogEntry(
        topic="industrial.dlq",
        stage="dlq",
        description="Rejected or oversized industrial events requiring operator review.",
        category="industrial",
        producers=("validation", "edge.ingest", "rest.ingest"),
        consumers=("dlq.review", "replay", "operations"),
        site_scoped=True,
        retained=True,
    ),
    EventCatalogEntry(
        topic="iot.raw",
        stage="compatibility",
        description="Legacy compatibility stream for older processor contracts.",
        category="industrial",
        producers=("edge.ingest",),
        consumers=("runtime.processor", "flink.job"),
        site_scoped=True,
        retained=True,
    ),
    EventCatalogEntry(
        topic="iot.processed",
        stage="processed",
        description="Windowed and scored telemetry produced by stream processing.",
        category="industrial",
        producers=("runtime.processor", "flink.job"),
        consumers=("ai.gateway", "historian.fanout", "dashboard"),
        site_scoped=True,
        retained=True,
    ),
    EventCatalogEntry(
        topic="iot.ai_enriched",
        stage="enriched",
        description="Versioned AI summaries and annotations for downstream operators.",
        category="ai",
        producers=("ai.gateway",),
        consumers=("ai.fanout", "historian.ai_enriched", "dashboard"),
        site_scoped=True,
        retained=True,
    ),
)


def _manifest_topics(manifest_path: Path | str) -> list[dict[str, Any]]:
    try:
        manifest = load_project_manifest(manifest_path)
    except Exception:
        return []
    topics: list[dict[str, Any]] = []
    for source in manifest.sources:
        topics.append(
            {
                "topic": source.topic,
                "source_id": source.source_id,
                "site_id": source.site_id,
                "source_protocol": source.source_protocol,
                "asset_id": source.asset_id,
                "line": source.line,
                "tags": list(source.tags),
            }
        )
    return topics


def build_event_catalog_snapshot(
    *,
    project_manifest_path: Path | str = Path("config/project-manifest.yaml"),
) -> dict[str, Any]:
    manifest_topics = [item for item in _manifest_topics(project_manifest_path) if item.get("topic")]
    manifest_topic_names = sorted({str(item["topic"]) for item in manifest_topics})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_topics": [entry.to_dict() for entry in CANONICAL_EVENT_TOPICS],
        "ai_event_contracts": [contract.to_dict() for contract in AI_EVENT_CONTRACTS],
        "project_topics": manifest_topics,
        "topic_names": manifest_topic_names,
        "counts": {
            "canonical_topics": len(CANONICAL_EVENT_TOPICS),
            "ai_event_contracts": len(AI_EVENT_CONTRACTS),
            "project_topics": len(manifest_topics),
            "site_scoped_topics": sum(1 for topic in CANONICAL_EVENT_TOPICS if topic.site_scoped),
            "categories": sorted({topic.category for topic in CANONICAL_EVENT_TOPICS}),
        },
        "contracts": {
            "logical_catalog": True,
            "read_only": True,
            "topic_contracts": list(manifest_topic_names),
        },
        "notes": [
            "Canonical topics describe the platform Kafka contract.",
            "Project topics describe how a company maps its own sources onto that contract.",
            "The catalog is read-only and does not replace the project manifest.",
        ],
    }
