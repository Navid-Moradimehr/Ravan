from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel, Field

from services.common.semantic_core import (
    OntologyPack,
    SemanticAction,
    SemanticDocument,
    SemanticEntity,
    SemanticEvent,
    SemanticMeasurement,
    SemanticObservation,
    SemanticRelationship,
    SemanticState,
    SemanticWorkflow,
    build_semantic_core_catalog,
)
from services.common.semantic_store import SemanticLineageRecord, get_semantic_store


router = APIRouter(tags=["semantic"])
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ASSET_HIERARCHY = REPO_ROOT / "config" / "assets.yaml"


def _semantic_graph():
    return get_semantic_store().graph()


class OntologyPackRequest(BaseModel):
    pack_id: str
    name: str
    layer: str = "platform"
    version: str = "1.0"
    concepts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SemanticEntityRequest(BaseModel):
    entity_id: str
    entity_type: str
    name: str = ""
    labels: list[str] = Field(default_factory=list)
    site_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticRelationshipRequest(BaseModel):
    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: str
    site_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticDocumentRequest(BaseModel):
    document_id: str
    title: str
    document_type: str = "document"
    uri: str = ""
    site_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticWorkflowRequest(BaseModel):
    workflow_id: str
    name: str
    workflow_type: str = "workflow"
    site_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticObservationRequest(BaseModel):
    observation_id: str
    entity_id: str
    observed_at: str
    value: Any
    source_id: str = ""
    site_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticLineageRequest(BaseModel):
    lineage_id: str
    kind: str
    source_id: str
    target_id: str = ""
    entity_id: str = ""
    relationship_id: str = ""
    site_id: str = ""
    dataset_id: str = ""
    model_version: str = ""
    processing_version: str = ""
    occurred_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/v1/semantic/core")
async def get_semantic_core() -> dict[str, Any]:
    return build_semantic_core_catalog()


@router.get("/api/v1/semantic/graph")
async def get_semantic_graph() -> dict[str, Any]:
    return _semantic_graph().to_dict()


@router.get("/api/v1/semantic/graph/search")
async def search_semantic_graph(q: str, limit: int = 10, site_id: str | None = None) -> dict[str, Any]:
    return _semantic_graph().graph_search(q, limit=limit, site_id=site_id)


@router.get("/api/v1/semantic/graph/entities/{entity_id:path}")
async def get_semantic_entity(entity_id: str) -> dict[str, Any]:
    graph = _semantic_graph()
    entity = graph.entities.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity.to_dict()


@router.get("/api/v1/semantic/graph/relationships/{relationship_id:path}")
async def get_semantic_relationship(relationship_id: str) -> dict[str, Any]:
    graph = _semantic_graph()
    relationship = graph.relationships.get(relationship_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return relationship.to_dict()


@router.get("/api/v1/semantic/ontology-packs")
async def list_ontology_packs() -> dict[str, Any]:
    store = get_semantic_store()
    return {"ontology_packs": store.list_ontology_packs()}


@router.post("/api/v1/semantic/ontology-packs")
async def upsert_ontology_pack(req: OntologyPackRequest) -> dict[str, Any]:
    store = get_semantic_store()
    pack = OntologyPack(
        pack_id=req.pack_id,
        name=req.name,
        layer=req.layer,
        version=req.version,
        concepts=tuple(req.concepts),
        notes=tuple(req.notes),
    )
    return store.upsert_ontology_pack(pack)


@router.post("/api/v1/semantic/entities")
async def upsert_semantic_entity(req: SemanticEntityRequest) -> dict[str, Any]:
    store = get_semantic_store()
    entity = SemanticEntity(
        entity_id=req.entity_id,
        entity_type=req.entity_type,
        name=req.name,
        labels=tuple(req.labels),
        metadata={**req.metadata, **({"site_id": req.site_id} if req.site_id else {})},
    )
    return store.upsert_entity(entity)


@router.post("/api/v1/semantic/relationships")
async def upsert_semantic_relationship(req: SemanticRelationshipRequest) -> dict[str, Any]:
    store = get_semantic_store()
    relationship = SemanticRelationship(
        relationship_id=req.relationship_id,
        source_id=req.source_id,
        target_id=req.target_id,
        relationship_type=req.relationship_type,
        metadata={**req.metadata, **({"site_id": req.site_id} if req.site_id else {})},
    )
    return store.upsert_relationship(relationship)


@router.post("/api/v1/semantic/documents")
async def upsert_semantic_document(req: SemanticDocumentRequest) -> dict[str, Any]:
    store = get_semantic_store()
    document = SemanticDocument(
        document_id=req.document_id,
        title=req.title,
        document_type=req.document_type,
        uri=req.uri,
        metadata={**req.metadata, **({"site_id": req.site_id} if req.site_id else {})},
    )
    return store.upsert_document(document)


@router.post("/api/v1/semantic/workflows")
async def upsert_semantic_workflow(req: SemanticWorkflowRequest) -> dict[str, Any]:
    store = get_semantic_store()
    workflow = SemanticWorkflow(
        workflow_id=req.workflow_id,
        name=req.name,
        workflow_type=req.workflow_type,
        metadata={**req.metadata, **({"site_id": req.site_id} if req.site_id else {})},
    )
    return store.upsert_workflow(workflow)


@router.post("/api/v1/semantic/observations")
async def upsert_semantic_observation(req: SemanticObservationRequest) -> dict[str, Any]:
    store = get_semantic_store()
    observation = SemanticObservation(
        observation_id=req.observation_id,
        entity_id=req.entity_id,
        observed_at=req.observed_at,
        value=req.value,
        source_id=req.source_id,
        metadata={**req.metadata, **({"site_id": req.site_id} if req.site_id else {})},
    )
    return store.upsert_observation(observation)


@router.post("/api/v1/semantic/lineage")
async def record_semantic_lineage(req: SemanticLineageRequest) -> dict[str, Any]:
    store = get_semantic_store()
    lineage = SemanticLineageRecord(
        lineage_id=req.lineage_id,
        kind=req.kind,
        source_id=req.source_id,
        target_id=req.target_id,
        entity_id=req.entity_id,
        relationship_id=req.relationship_id,
        site_id=req.site_id,
        dataset_id=req.dataset_id,
        model_version=req.model_version,
        processing_version=req.processing_version,
        occurred_at=req.occurred_at,
        metadata=req.metadata,
    )
    return store.record_lineage(lineage)


@router.get("/api/v1/semantic/lineage")
async def list_semantic_lineage(site_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    store = get_semantic_store()
    return {"lineage": store.list_lineage(site_id=site_id, limit=limit)}
