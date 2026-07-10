from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.common.modeling import ModelRegistry
from services.common.dataset_builder import build_dataset_builder_snapshot
from services.common.asset_registry import build_asset_registry_snapshot
from services.common.connection_registry import connection_registry
from services.common.event_catalog import build_event_catalog_snapshot
from services.common.operational_memory import build_operational_memory_snapshot
from services.common.prompt_registry import prompt_registry
from services.common.retrieval import build_retrieval_catalog
from services.common.schema_registry import schema_registry
from services.common.semantic_core import build_semantic_core_catalog
from services.common.semantic_store import get_semantic_store
from services.datasets.runtime_catalog import list_dataset_sources


PLATFORM_CORE_OWNERSHIP = (
    "industrial event model",
    "Kafka contracts",
    "historian",
    "replay",
    "metadata contracts",
    "semantic primitives",
    "AI gateway contracts",
    "benchmark framework",
)

USER_OWNED_BOUNDARIES = (
    "industrial processes",
    "MES",
    "ERP",
    "plant topology",
    "secrets",
    "infrastructure",
    "GPU sizing",
    "retention policies",
    "company-specific ontologies",
)

HISTORICAL_MEMORY = {
    "name": "Historical Memory",
    "description": "Telemetry, alarms, historian writes, and replayable operational measurements.",
    "status": "implemented",
    "sources": ("historian.events", "historian.alarms", "historian.trend"),
}

SEMANTIC_MEMORY = {
    "name": "Semantic Memory",
    "description": "Assets, topology, ontology packs, relationships, and lineage.",
    "status": "implemented",
    "sources": ("semantic.core", "semantic.graph", "semantic.ontology_packs", "semantic.lineage"),
}

DATA_PLANE = {
    "name": "Data Plane",
    "description": "Ingestion, Kafka, processing, and storage paths that move operational events through the platform.",
    "status": "implemented",
    "sources": ("edge.ingest", "kafka", "runtime.processor", "historian", "lakehouse"),
}

CONTROL_PLANE = {
    "name": "Control Plane",
    "description": "Metadata, schema registry, lineage, catalog, governance, and policy contracts.",
    "status": "implemented",
    "sources": ("metadata", "schema registry", "lineage", "event catalog", "dataset builder", "governance"),
}

INTELLIGENCE_PLANE = {
    "name": "Intelligence Plane",
    "description": "AI gateway, retrieval, semantic reasoning, and curated AI outputs.",
    "status": "implemented",
    "sources": ("ai gateway", "retrieval", "semantic core", "ai events"),
}

OPERATIONAL_MEMORY = {
    "name": "Operational Memory",
    "description": "Maintenance, operator actions, shifts, recipes, work orders, approvals, and incident history.",
    "status": "planned",
    "sources": ("project manifest", "site profile", "workflow hooks", "operator inputs"),
}


@dataclass(frozen=True)
class MetadataPlaneSection:
    name: str
    description: str
    status: str
    sources: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _model_registry_for(site_profile_path: Path | str | None) -> ModelRegistry:
    if site_profile_path is None:
        return ModelRegistry.from_env()

    from services.common.site_profiles import load_site_profile

    profile = load_site_profile(site_profile_path)
    return ModelRegistry.from_site_profile(profile)


def build_metadata_plane_snapshot(
    *,
    site_profile_path: Path | str | None = None,
    asset_config: Path | str = Path("config/assets.yaml"),
    semantic_store_path: Path | str | None = None,
) -> dict[str, Any]:
    """Build a lightweight logical metadata-plane snapshot."""

    store = get_semantic_store(semantic_store_path)
    semantic_snapshot = store.snapshot()
    semantic_graph = semantic_snapshot.get("graph", {})
    lineage = list(semantic_snapshot.get("lineage", []))
    model_registry = _model_registry_for(site_profile_path)
    schema_summaries = schema_registry.list_schemas()
    operational_snapshot = build_operational_memory_snapshot()
    asset_registry = build_asset_registry_snapshot(asset_config=asset_config)
    event_catalog = build_event_catalog_snapshot()
    dataset_builder = build_dataset_builder_snapshot()

    sections = (
        MetadataPlaneSection(**DATA_PLANE),
        MetadataPlaneSection(**CONTROL_PLANE),
        MetadataPlaneSection(**INTELLIGENCE_PLANE),
        MetadataPlaneSection(**HISTORICAL_MEMORY),
        MetadataPlaneSection(**SEMANTIC_MEMORY),
        MetadataPlaneSection(**OPERATIONAL_MEMORY),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plane": "logical-metadata-plane",
        "ownership": {
            "platform_core": list(PLATFORM_CORE_OWNERSHIP),
            "user_owned": list(USER_OWNED_BOUNDARIES),
        },
        "planes": {
            "data": DATA_PLANE,
            "control": CONTROL_PLANE,
            "intelligence": INTELLIGENCE_PLANE,
        },
        "memory_layers": [section.to_dict() for section in sections],
        "registries": {
            "asset_registry": asset_registry,
            "connections": connection_registry.export(),
            "schemas": schema_summaries,
            "models": model_registry.export(),
            "prompts": prompt_registry.list_templates(),
            "datasets": [dataset.__dict__ for dataset in list_dataset_sources()],
        },
        "dataset_builder": dataset_builder,
        "catalogs": {
            "semantic_core": build_semantic_core_catalog(),
            "retrieval": build_retrieval_catalog(asset_config=asset_config),
            "event_catalog": event_catalog,
        },
        "semantic_store": {
            "backend": semantic_snapshot.get("path", ""),
            "counts": semantic_graph.get("counts", {}),
            "ontology_pack_count": len(semantic_graph.get("ontology_packs", [])),
            "lineage_count": len(lineage),
            "recent_lineage": lineage[:10],
        },
        "operational_memory": {
            "sections": operational_snapshot["sections"],
            "alerts": operational_snapshot["alerts"],
            "annotations_count": len(operational_snapshot["annotations"]),
            "shifts": operational_snapshot["shifts"],
            "reports": operational_snapshot["reports"],
            "backups": operational_snapshot["backups"],
            "contracts": operational_snapshot["contracts"],
        },
        "contracts": {
            "schema_compatibility_modes": sorted({schema["compatibility"] for schema in schema_summaries}),
            "metadata_is_read_only": True,
            "metadata_is_logical": True,
            "semantic_store_backend": semantic_snapshot.get("path", ""),
            "asset_registry_entries": asset_registry["entry_count"],
            "event_catalog_topics": event_catalog["counts"]["canonical_topics"],
            "dataset_builder_contract": dataset_builder["contracts"]["logical_contract"],
        },
        "notes": [
            "Historian answers what happened.",
            "Metadata answers what exists and how it is governed.",
            "Semantic layer answers how things are related.",
            "The control plane carries contracts and governance, not historian telemetry.",
            "The intelligence plane consumes curated data and semantic context instead of raw historian tables directly.",
            "Operational memory is documented now but remains largely user-owned in the current release.",
        ],
    }
