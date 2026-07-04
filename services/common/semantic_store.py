from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.common.semantic_core import (
    OntologyPack,
    SemanticAction,
    SemanticDocument,
    SemanticEntity,
    SemanticEvent,
    SemanticGraph,
    SemanticLocation,
    SemanticMeasurement,
    SemanticObservation,
    SemanticRelationship,
    SemanticState,
    SemanticWorkflow,
    load_semantic_graph_from_assets,
)


DEFAULT_SEMANTIC_STORE_PATH = Path("data/semantic/semantic-store.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(path)


def _coerce_semantic_graph(payload: dict[str, Any] | None) -> SemanticGraph:
    if payload:
        if isinstance(payload.get("graph"), dict):
            return SemanticGraph.from_dict(payload["graph"])
        return SemanticGraph.from_dict(payload)
    return load_semantic_graph_from_assets(Path("config/assets.yaml"))


@dataclass(frozen=True)
class SemanticLineageRecord:
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
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FileSemanticStoreBackend:
    """File-backed semantic graph store used for offline development and tests."""

    def __init__(self, path: Path | str = DEFAULT_SEMANTIC_STORE_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._graph = self._load_graph()
        self._lineage: dict[str, SemanticLineageRecord] = self._load_lineage()

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load_graph(self) -> SemanticGraph:
        return _coerce_semantic_graph(self._read_payload())

    def _load_lineage(self) -> dict[str, SemanticLineageRecord]:
        payload = self._read_payload()
        lineage: dict[str, SemanticLineageRecord] = {}
        for item in payload.get("lineage", []):
            if not item.get("lineage_id"):
                continue
            lineage[str(item["lineage_id"])] = SemanticLineageRecord(
                lineage_id=str(item.get("lineage_id", "")),
                kind=str(item.get("kind", "unknown")),
                source_id=str(item.get("source_id", "")),
                target_id=str(item.get("target_id", "")),
                entity_id=str(item.get("entity_id", "")),
                relationship_id=str(item.get("relationship_id", "")),
                site_id=str(item.get("site_id", "")),
                dataset_id=str(item.get("dataset_id", "")),
                model_version=str(item.get("model_version", "")),
                processing_version=str(item.get("processing_version", "")),
                occurred_at=str(item.get("occurred_at", "")),
                metadata=dict(item.get("metadata", {})),
            )
        return lineage

    def _save(self) -> None:
        payload = {
            "version": 1,
            "updated_at": _utc_now(),
            "graph": self._graph.to_dict(),
            "lineage": [record.to_dict() for record in self._lineage.values()],
        }
        _atomic_write(self.path, json.dumps(payload, indent=2, ensure_ascii=False))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "path": str(self.path),
                "updated_at": _utc_now(),
                "graph": self._graph.to_dict(),
                "lineage": [record.to_dict() for record in self._lineage.values()],
            }

    def graph(self) -> SemanticGraph:
        with self._lock:
            return self._graph.clone()

    def replace_graph(self, graph: SemanticGraph) -> dict[str, Any]:
        with self._lock:
            self._graph = graph.clone()
            self._save()
            return {
                "path": str(self.path),
                "updated_at": _utc_now(),
                "graph": self._graph.to_dict(),
                "lineage": [record.to_dict() for record in self._lineage.values()],
            }

    def upsert_ontology_pack(self, pack: OntologyPack) -> dict[str, Any]:
        with self._lock:
            existing = {item.pack_id: item for item in self._graph.ontology_packs}
            existing[pack.pack_id] = pack
            self._graph.ontology_packs = list(existing.values())
            self._save()
            return pack.to_dict()

    def list_ontology_packs(self) -> list[dict[str, Any]]:
        return [pack.to_dict() for pack in self.graph().ontology_packs]

    def _upsert_graph_item(self, collection: dict[str, Any], item: Any, key: str) -> dict[str, Any]:
        with self._lock:
            collection[key] = item
            self._save()
            return item.to_dict()

    def upsert_entity(self, entity: SemanticEntity) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.entities, entity, entity.entity_id)

    def upsert_relationship(self, relationship: SemanticRelationship) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.relationships, relationship, relationship.relationship_id)

    def upsert_measurement(self, measurement: SemanticMeasurement) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.measurements, measurement, measurement.measurement_id)

    def upsert_observation(self, observation: SemanticObservation) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.observations, observation, observation.observation_id)

    def upsert_action(self, action: SemanticAction) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.actions, action, action.action_id)

    def upsert_document(self, document: SemanticDocument) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.documents, document, document.document_id)

    def upsert_location(self, location: SemanticLocation) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.locations, location, location.location_id)

    def upsert_state(self, state: SemanticState) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.states, state, state.state_id)

    def upsert_workflow(self, workflow: SemanticWorkflow) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.workflows, workflow, workflow.workflow_id)

    def upsert_event(self, event: SemanticEvent) -> dict[str, Any]:
        return self._upsert_graph_item(self._graph.events, event, event.event_id)

    def record_lineage(self, record: SemanticLineageRecord) -> dict[str, Any]:
        with self._lock:
            self._lineage[record.lineage_id] = record
            self._save()
            return record.to_dict()

    def list_lineage(self, *, site_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        records = list(self._lineage.values())
        if site_id:
            records = [record for record in records if record.site_id == site_id]
        records.sort(key=lambda record: (record.occurred_at, record.lineage_id), reverse=True)
        return [record.to_dict() for record in records[: max(1, limit)]]


class DatabaseSemanticStoreBackend:
    """Postgres-backed semantic graph store used in production."""

    def _graph(self) -> SemanticGraph:
        from services.historian import client as historian_client

        return SemanticGraph.from_dict(historian_client.load_semantic_graph())

    def snapshot(self) -> dict[str, Any]:
        graph = self._graph()
        return {
            "path": "postgres://timescale/semantic",
            "updated_at": _utc_now(),
            "graph": graph.to_dict(),
            "lineage": self.list_lineage(limit=1000),
        }

    def graph(self) -> SemanticGraph:
        return self._graph()

    def replace_graph(self, graph: SemanticGraph) -> dict[str, Any]:
        from services.historian import client as historian_client

        historian_client.replace_semantic_graph(graph)
        return self.snapshot()

    def upsert_ontology_pack(self, pack: OntologyPack) -> dict[str, Any]:
        graph = self._graph()
        existing = {item.pack_id: item for item in graph.ontology_packs}
        existing[pack.pack_id] = pack
        graph.ontology_packs = list(existing.values())
        self.replace_graph(graph)
        return pack.to_dict()

    def list_ontology_packs(self) -> list[dict[str, Any]]:
        return [pack.to_dict() for pack in self._graph().ontology_packs]

    def _upsert_graph_item(
        self,
        collection_name: str,
        item: Any,
        key_column: str,
        *,
        json_columns: set[str] | None = None,
    ) -> dict[str, Any]:
        from services.historian import client as historian_client

        row = {key: list(value) if isinstance(value, tuple) else value for key, value in item.to_dict().items()}
        historian_client._semantic_upsert(  # type: ignore[attr-defined]
            collection_name,
            key_column,
            row,
            json_columns=json_columns or ({"metadata", "payload", "value"} if "payload" in row or "value" in row else {"metadata"}),
        )
        return row

    def upsert_entity(self, entity: SemanticEntity) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_entities", entity, "entity_id")

    def upsert_relationship(self, relationship: SemanticRelationship) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_relationships", relationship, "relationship_id")

    def upsert_measurement(self, measurement: SemanticMeasurement) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_measurements", measurement, "measurement_id")

    def upsert_observation(self, observation: SemanticObservation) -> dict[str, Any]:
        return self._upsert_graph_item(
            "semantic_observations",
            observation,
            "observation_id",
            json_columns={"metadata", "value"},
        )

    def upsert_action(self, action: SemanticAction) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_actions", action, "action_id")

    def upsert_document(self, document: SemanticDocument) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_documents", document, "document_id")

    def upsert_location(self, location: SemanticLocation) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_locations", location, "location_id")

    def upsert_state(self, state: SemanticState) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_states", state, "state_id")

    def upsert_workflow(self, workflow: SemanticWorkflow) -> dict[str, Any]:
        return self._upsert_graph_item("semantic_workflows", workflow, "workflow_id")

    def upsert_event(self, event: SemanticEvent) -> dict[str, Any]:
        return self._upsert_graph_item(
            "semantic_events",
            event,
            "event_id",
            json_columns={"metadata", "payload"},
        )

    def record_lineage(self, record: SemanticLineageRecord) -> dict[str, Any]:
        from services.historian import client as historian_client

        return historian_client.upsert_semantic_lineage(record.to_dict())

    def list_lineage(self, *, site_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        from services.historian import client as historian_client

        rows = historian_client.list_semantic_lineage(site_id=site_id, limit=limit)
        return rows


class SemanticStore:
    """Facade that chooses the right semantic persistence backend."""

    def __init__(self, backend: FileSemanticStoreBackend | DatabaseSemanticStoreBackend):
        self._backend = backend

    def snapshot(self) -> dict[str, Any]:
        return self._backend.snapshot()

    def graph(self) -> SemanticGraph:
        return self._backend.graph()

    def replace_graph(self, graph: SemanticGraph) -> dict[str, Any]:
        return self._backend.replace_graph(graph)

    def upsert_ontology_pack(self, pack: OntologyPack) -> dict[str, Any]:
        return self._backend.upsert_ontology_pack(pack)

    def list_ontology_packs(self) -> list[dict[str, Any]]:
        return self._backend.list_ontology_packs()

    def upsert_entity(self, entity: SemanticEntity) -> dict[str, Any]:
        return self._backend.upsert_entity(entity)

    def upsert_relationship(self, relationship: SemanticRelationship) -> dict[str, Any]:
        return self._backend.upsert_relationship(relationship)

    def upsert_measurement(self, measurement: SemanticMeasurement) -> dict[str, Any]:
        return self._backend.upsert_measurement(measurement)

    def upsert_observation(self, observation: SemanticObservation) -> dict[str, Any]:
        return self._backend.upsert_observation(observation)

    def upsert_action(self, action: SemanticAction) -> dict[str, Any]:
        return self._backend.upsert_action(action)

    def upsert_document(self, document: SemanticDocument) -> dict[str, Any]:
        return self._backend.upsert_document(document)

    def upsert_location(self, location: SemanticLocation) -> dict[str, Any]:
        return self._backend.upsert_location(location)

    def upsert_state(self, state: SemanticState) -> dict[str, Any]:
        return self._backend.upsert_state(state)

    def upsert_workflow(self, workflow: SemanticWorkflow) -> dict[str, Any]:
        return self._backend.upsert_workflow(workflow)

    def upsert_event(self, event: SemanticEvent) -> dict[str, Any]:
        return self._backend.upsert_event(event)

    def record_lineage(self, record: SemanticLineageRecord) -> dict[str, Any]:
        return self._backend.record_lineage(record)

    def list_lineage(self, *, site_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self._backend.list_lineage(site_id=site_id, limit=limit)


def _should_use_database_backend(path: Path | str | None) -> bool:
    if path is not None:
        return False
    backend = os.getenv("SEMANTIC_STORE_BACKEND", "auto").lower().strip()
    if backend in {"file", "json"}:
        return False
    if backend in {"db", "postgres", "timescale"}:
        return True
    return True


def get_semantic_store(path: Path | str | None = None) -> SemanticStore:
    if path is None:
        path = os.getenv("SEMANTIC_STORE_PATH")
        if path:
            return SemanticStore(FileSemanticStoreBackend(path))
        if _should_use_database_backend(None):
            try:
                backend = DatabaseSemanticStoreBackend()
                backend.list_ontology_packs()
                return SemanticStore(backend)
            except Exception:
                return SemanticStore(FileSemanticStoreBackend(DEFAULT_SEMANTIC_STORE_PATH))
        return SemanticStore(FileSemanticStoreBackend(DEFAULT_SEMANTIC_STORE_PATH))
    return SemanticStore(FileSemanticStoreBackend(path))
