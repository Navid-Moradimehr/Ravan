from __future__ import annotations

from pathlib import Path

from services.assets.model import load_hierarchy
from services.common.semantic_core import PLATFORM_PRIMITIVES, build_semantic_core_catalog


def test_semantic_core_catalog_exposes_platform_primitives() -> None:
    catalog = build_semantic_core_catalog()

    assert catalog["platform_primitives"] == list(PLATFORM_PRIMITIVES)
    assert len(catalog["ontology_packs"]) >= 2
    assert catalog["summary"]["ontology_packs"] == 2


def test_asset_hierarchy_projects_to_semantic_graph() -> None:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    graph = hierarchy.to_semantic_graph("config/assets.yaml")

    assert graph.counts()["entities"] > 0
    assert graph.counts()["relationships"] > 0
    assert graph.counts()["measurements"] == 9
    assert any(entity.entity_type == "site" for entity in graph.entities.values())
    assert any(relationship.relationship_type == "contains" for relationship in graph.relationships.values())


def test_semantic_graph_contains_source_document() -> None:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    graph = hierarchy.to_semantic_graph("config/assets.yaml")

    assert "document:config/assets.yaml" in graph.documents
