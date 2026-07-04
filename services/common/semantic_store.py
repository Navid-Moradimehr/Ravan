from __future__ import annotations

import json
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


class SemanticStore:
    """File-backed semantic graph store used for the platform semantic plane."""

    def __init__(self, path: Path | str = DEFAULT_SEMANTIC_STORE_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._graph = self._load()
        self._lineage: dict[str, SemanticLineageRecord] = {
            str(item.get("lineage_id", "")): SemanticLineageRecord(
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
            for item in self._read_payload().get("lineage", [])
            if item.get("lineage_id")
        }

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load(self) -> SemanticGraph:
        payload = self._read_payload()
        if payload:
            if isinstance(payload.get("graph"), dict):
                return SemanticGraph.from_dict(payload["graph"])
            return SemanticGraph.from_dict(payload)
        return load_semantic_graph_from_assets(Path("config/assets.yaml"))

    def _save(self) -> None:
        payload = {
            "version": 1,
            "updated_at": _utc_now(),
            "graph": self._graph.to_dict(),
            "lineage": [record.to_dict() for record in self._lineage.values()],
        }
        _atomic_write(self.path, json.dumps(payload, indent=2, ensure_ascii=False))

    def _snapshot_unlocked(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "updated_at": _utc_now(),
            "graph": self._graph.to_dict(),
            "lineage": [record.to_dict() for record in self._lineage.values()],
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot_unlocked()

    def graph(self) -> SemanticGraph:
        with self._lock:
            return self._graph.clone()

    def replace_graph(self, graph: SemanticGraph) -> dict[str, Any]:
        with self._lock:
            self._graph = graph.clone()
            self._save()
            return self._snapshot_unlocked()

    def upsert_ontology_pack(self, pack: OntologyPack) -> dict[str, Any]:
        with self._lock:
            existing = {item.pack_id: item for item in self._graph.ontology_packs}
            existing[pack.pack_id] = pack
            self._graph.ontology_packs = list(existing.values())
            self._save()
            return pack.to_dict()

    def list_ontology_packs(self) -> list[dict[str, Any]]:
        return [pack.to_dict() for pack in self.graph().ontology_packs]

    def upsert_entity(self, entity: SemanticEntity) -> dict[str, Any]:
        with self._lock:
            self._graph.entities[entity.entity_id] = entity
            self._save()
            return entity.to_dict()

    def upsert_relationship(self, relationship: SemanticRelationship) -> dict[str, Any]:
        with self._lock:
            self._graph.relationships[relationship.relationship_id] = relationship
            self._save()
            return relationship.to_dict()

    def upsert_measurement(self, measurement: SemanticMeasurement) -> dict[str, Any]:
        with self._lock:
            self._graph.measurements[measurement.measurement_id] = measurement
            self._save()
            return measurement.to_dict()

    def upsert_observation(self, observation: SemanticObservation) -> dict[str, Any]:
        with self._lock:
            self._graph.observations[observation.observation_id] = observation
            self._save()
            return observation.to_dict()

    def upsert_action(self, action: SemanticAction) -> dict[str, Any]:
        with self._lock:
            self._graph.actions[action.action_id] = action
            self._save()
            return action.to_dict()

    def upsert_document(self, document: SemanticDocument) -> dict[str, Any]:
        with self._lock:
            self._graph.documents[document.document_id] = document
            self._save()
            return document.to_dict()

    def upsert_location(self, location: SemanticLocation) -> dict[str, Any]:
        with self._lock:
            self._graph.locations[location.location_id] = location
            self._save()
            return location.to_dict()

    def upsert_state(self, state: SemanticState) -> dict[str, Any]:
        with self._lock:
            self._graph.states[state.state_id] = state
            self._save()
            return state.to_dict()

    def upsert_workflow(self, workflow: SemanticWorkflow) -> dict[str, Any]:
        with self._lock:
            self._graph.workflows[workflow.workflow_id] = workflow
            self._save()
            return workflow.to_dict()

    def upsert_event(self, event: SemanticEvent) -> dict[str, Any]:
        with self._lock:
            self._graph.events[event.event_id] = event
            self._save()
            return event.to_dict()

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


def get_semantic_store(path: Path | str | None = None) -> SemanticStore:
    if path is None:
        import os

        path = os.getenv("SEMANTIC_STORE_PATH", str(DEFAULT_SEMANTIC_STORE_PATH))
    return SemanticStore(path)
