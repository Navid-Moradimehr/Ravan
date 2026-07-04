from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PLATFORM_PRIMITIVES = (
    "Entity",
    "Relationship",
    "Event",
    "Observation",
    "Measurement",
    "State",
    "Action",
    "Document",
    "Location",
    "Policy",
    "Time",
    "Workflow",
    "Schema",
    "Lineage",
)

DEFAULT_ONTOLOGY_PACKS = (
    {
        "pack_id": "platform.core",
        "name": "Platform Core",
        "layer": "platform",
        "version": "1.0",
        "concepts": PLATFORM_PRIMITIVES,
        "notes": ("Universal primitives used by every installation.",),
    },
    {
        "pack_id": "industry.manufacturing",
        "name": "Manufacturing Pack",
        "layer": "industry",
        "version": "1.0",
        "concepts": ("Site", "Area", "Line", "Cell", "Asset", "Tag", "Shift", "Batch", "Recipe", "Machine", "Operator", "WorkOrder", "Product", "OEE"),
        "notes": ("First domain pack for the current industrial app.",),
    },
)


@dataclass(frozen=True)
class OntologyPack:
    pack_id: str
    name: str
    layer: str
    version: str
    concepts: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticEntity:
    entity_id: str
    entity_type: str
    name: str = ""
    labels: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticRelationship:
    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticMeasurement:
    measurement_id: str
    entity_id: str
    name: str
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    sampling_rate_hz: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticObservation:
    observation_id: str
    entity_id: str
    observed_at: str
    value: Any
    source_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticAction:
    action_id: str
    actor_id: str
    target_id: str
    action_type: str
    occurred_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticDocument:
    document_id: str
    title: str
    document_type: str = "document"
    uri: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticLocation:
    location_id: str
    name: str
    location_type: str
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticState:
    state_id: str
    entity_id: str
    state: str
    valid_from: str
    valid_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticWorkflow:
    workflow_id: str
    name: str
    workflow_type: str = "workflow"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticEvent:
    event_id: str
    event_type: str
    occurred_at: str
    source_id: str = ""
    entity_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticGraph:
    ontology_packs: list[OntologyPack] = field(default_factory=list)
    entities: dict[str, SemanticEntity] = field(default_factory=dict)
    relationships: dict[str, SemanticRelationship] = field(default_factory=dict)
    measurements: dict[str, SemanticMeasurement] = field(default_factory=dict)
    observations: dict[str, SemanticObservation] = field(default_factory=dict)
    actions: dict[str, SemanticAction] = field(default_factory=dict)
    documents: dict[str, SemanticDocument] = field(default_factory=dict)
    locations: dict[str, SemanticLocation] = field(default_factory=dict)
    states: dict[str, SemanticState] = field(default_factory=dict)
    workflows: dict[str, SemanticWorkflow] = field(default_factory=dict)
    events: dict[str, SemanticEvent] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "SemanticGraph":
        graph = cls()
        for pack in DEFAULT_ONTOLOGY_PACKS:
            graph.ontology_packs.append(
                OntologyPack(
                    pack_id=pack["pack_id"],
                    name=pack["name"],
                    layer=pack["layer"],
                    version=pack["version"],
                    concepts=tuple(pack["concepts"]),
                    notes=tuple(pack["notes"]),
                )
            )
        return graph

    def add_entity(self, entity: SemanticEntity) -> None:
        self.entities[entity.entity_id] = entity

    def add_relationship(self, relationship: SemanticRelationship) -> None:
        self.relationships[relationship.relationship_id] = relationship

    def add_measurement(self, measurement: SemanticMeasurement) -> None:
        self.measurements[measurement.measurement_id] = measurement

    def add_document(self, document: SemanticDocument) -> None:
        self.documents[document.document_id] = document

    def add_location(self, location: SemanticLocation) -> None:
        self.locations[location.location_id] = location

    def add_workflow(self, workflow: SemanticWorkflow) -> None:
        self.workflows[workflow.workflow_id] = workflow

    def add_event(self, event: SemanticEvent) -> None:
        self.events[event.event_id] = event

    def counts(self) -> dict[str, int]:
        return {
            "ontology_packs": len(self.ontology_packs),
            "entities": len(self.entities),
            "relationships": len(self.relationships),
            "measurements": len(self.measurements),
            "observations": len(self.observations),
            "actions": len(self.actions),
            "documents": len(self.documents),
            "locations": len(self.locations),
            "states": len(self.states),
            "workflows": len(self.workflows),
            "events": len(self.events),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticGraph":
        graph = cls()
        graph.ontology_packs = [
            OntologyPack(
                pack_id=str(item.get("pack_id", "")),
                name=str(item.get("name", "")),
                layer=str(item.get("layer", "platform")),
                version=str(item.get("version", "1.0")),
                concepts=tuple(str(concept) for concept in item.get("concepts", []) if concept),
                notes=tuple(str(note) for note in item.get("notes", []) if note),
            )
            for item in data.get("ontology_packs", [])
            if item.get("pack_id")
        ]
        graph.entities = {
            str(item.get("entity_id", "")): SemanticEntity(
                entity_id=str(item.get("entity_id", "")),
                entity_type=str(item.get("entity_type", "entity")),
                name=str(item.get("name", "")),
                labels=tuple(str(label) for label in item.get("labels", []) if label),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("entities", [])
            if item.get("entity_id")
        }
        graph.relationships = {
            str(item.get("relationship_id", "")): SemanticRelationship(
                relationship_id=str(item.get("relationship_id", "")),
                source_id=str(item.get("source_id", "")),
                target_id=str(item.get("target_id", "")),
                relationship_type=str(item.get("relationship_type", "related_to")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("relationships", [])
            if item.get("relationship_id")
        }
        graph.measurements = {
            str(item.get("measurement_id", "")): SemanticMeasurement(
                measurement_id=str(item.get("measurement_id", "")),
                entity_id=str(item.get("entity_id", "")),
                name=str(item.get("name", "")),
                unit=str(item.get("unit", "")),
                minimum=item.get("minimum"),
                maximum=item.get("maximum"),
                warning_low=item.get("warning_low"),
                warning_high=item.get("warning_high"),
                critical_low=item.get("critical_low"),
                critical_high=item.get("critical_high"),
                sampling_rate_hz=item.get("sampling_rate_hz"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("measurements", [])
            if item.get("measurement_id")
        }
        graph.observations = {
            str(item.get("observation_id", "")): SemanticObservation(
                observation_id=str(item.get("observation_id", "")),
                entity_id=str(item.get("entity_id", "")),
                observed_at=str(item.get("observed_at", "")),
                value=item.get("value"),
                source_id=str(item.get("source_id", "")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("observations", [])
            if item.get("observation_id")
        }
        graph.actions = {
            str(item.get("action_id", "")): SemanticAction(
                action_id=str(item.get("action_id", "")),
                actor_id=str(item.get("actor_id", "")),
                target_id=str(item.get("target_id", "")),
                action_type=str(item.get("action_type", "")),
                occurred_at=str(item.get("occurred_at", "")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("actions", [])
            if item.get("action_id")
        }
        graph.documents = {
            str(item.get("document_id", "")): SemanticDocument(
                document_id=str(item.get("document_id", "")),
                title=str(item.get("title", "")),
                document_type=str(item.get("document_type", "document")),
                uri=str(item.get("uri", "")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("documents", [])
            if item.get("document_id")
        }
        graph.locations = {
            str(item.get("location_id", "")): SemanticLocation(
                location_id=str(item.get("location_id", "")),
                name=str(item.get("name", "")),
                location_type=str(item.get("location_type", "location")),
                parent_id=item.get("parent_id"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("locations", [])
            if item.get("location_id")
        }
        graph.states = {
            str(item.get("state_id", "")): SemanticState(
                state_id=str(item.get("state_id", "")),
                entity_id=str(item.get("entity_id", "")),
                state=str(item.get("state", "")),
                valid_from=str(item.get("valid_from", "")),
                valid_to=item.get("valid_to"),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("states", [])
            if item.get("state_id")
        }
        graph.workflows = {
            str(item.get("workflow_id", "")): SemanticWorkflow(
                workflow_id=str(item.get("workflow_id", "")),
                name=str(item.get("name", "")),
                workflow_type=str(item.get("workflow_type", "workflow")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("workflows", [])
            if item.get("workflow_id")
        }
        graph.events = {
            str(item.get("event_id", "")): SemanticEvent(
                event_id=str(item.get("event_id", "")),
                event_type=str(item.get("event_type", "")),
                occurred_at=str(item.get("occurred_at", "")),
                source_id=str(item.get("source_id", "")),
                entity_id=str(item.get("entity_id", "")),
                payload=dict(item.get("payload", {})),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("events", [])
            if item.get("event_id")
        }
        return graph

    def search_entities(self, query: str, *, limit: int = 10, site_id: str | None = None) -> list[SemanticEntity]:
        tokens = {part.lower() for part in query.replace("/", " ").replace("-", " ").split() if part}
        scored: list[tuple[int, SemanticEntity]] = []
        for entity in self.entities.values():
            if site_id and str(entity.metadata.get("site_id", "")).lower() != site_id.lower():
                continue
            score = 0
            candidate_terms = {entity.entity_id.lower(), entity.entity_type.lower(), entity.name.lower(), *{label.lower() for label in entity.labels}}
            candidate_terms.update(str(value).lower() for value in entity.metadata.values() if value is not None)
            for token in tokens:
                if token in candidate_terms:
                    score += 3
                elif any(token in term or term in token for term in candidate_terms):
                    score += 1
            if score > 0:
                scored.append((score, entity))
        scored.sort(key=lambda item: (-item[0], item[1].entity_id))
        return [entity for _, entity in scored[: max(1, limit)]]

    def search_relationships(self, query: str, *, limit: int = 10, site_id: str | None = None) -> list[SemanticRelationship]:
        tokens = {part.lower() for part in query.replace("/", " ").replace("-", " ").split() if part}
        scored: list[tuple[int, SemanticRelationship]] = []
        for relationship in self.relationships.values():
            if site_id and str(relationship.metadata.get("site_id", "")).lower() != site_id.lower():
                continue
            score = 0
            candidate_terms = {
                relationship.relationship_id.lower(),
                relationship.relationship_type.lower(),
                relationship.source_id.lower(),
                relationship.target_id.lower(),
            }
            candidate_terms.update(str(value).lower() for value in relationship.metadata.values() if value is not None)
            for token in tokens:
                if token in candidate_terms:
                    score += 3
                elif any(token in term or term in token for term in candidate_terms):
                    score += 1
            if score > 0:
                scored.append((score, relationship))
        scored.sort(key=lambda item: (-item[0], item[1].relationship_id))
        return [relationship for _, relationship in scored[: max(1, limit)]]

    def graph_search(self, query: str, *, limit: int = 10, site_id: str | None = None) -> dict[str, Any]:
        entities = self.search_entities(query, limit=limit, site_id=site_id)
        relationships = self.search_relationships(query, limit=limit, site_id=site_id)
        return {
            "query": query,
            "limit": limit,
            "site_id": site_id,
            "entities": [entity.to_dict() for entity in entities],
            "relationships": [relationship.to_dict() for relationship in relationships],
            "counts": {"entities": len(entities), "relationships": len(relationships)},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "ontology_packs": [pack.to_dict() for pack in self.ontology_packs],
            "entities": [entity.to_dict() for entity in self.entities.values()],
            "relationships": [relationship.to_dict() for relationship in self.relationships.values()],
            "measurements": [measurement.to_dict() for measurement in self.measurements.values()],
            "observations": [observation.to_dict() for observation in self.observations.values()],
            "actions": [action.to_dict() for action in self.actions.values()],
            "documents": [document.to_dict() for document in self.documents.values()],
            "locations": [location.to_dict() for location in self.locations.values()],
            "states": [state.to_dict() for state in self.states.values()],
            "workflows": [workflow.to_dict() for workflow in self.workflows.values()],
            "events": [event.to_dict() for event in self.events.values()],
            "counts": self.counts(),
        }

    def clone(self) -> "SemanticGraph":
        return SemanticGraph.from_dict(self.to_dict())

    @staticmethod
    def _node_id(*parts: str) -> str:
        return "/".join(part for part in parts if part)

    @classmethod
    def from_asset_hierarchy(cls, hierarchy: Any, *, source_uri: str = "config/assets.yaml") -> "SemanticGraph":
        graph = cls.default()
        graph.add_document(
            SemanticDocument(
                document_id=f"document:{source_uri}",
                title="Asset hierarchy source",
                document_type="configuration",
                uri=source_uri,
                metadata={"source_uri": source_uri},
            )
        )

        for site in getattr(hierarchy, "sites", {}).values():
            site_id = cls._node_id("site", site.id)
            graph.add_location(
                SemanticLocation(
                    location_id=site_id,
                    name=site.name,
                    location_type="site",
                    metadata={"source_type": "site", "site_id": site.id},
                )
            )
            graph.add_entity(
                SemanticEntity(
                    entity_id=site_id,
                    entity_type="site",
                    name=site.name,
                    labels=("site",),
                    metadata={"source_type": "site", "site_id": site.id},
                )
            )

            for area in site.areas.values():
                area_id = cls._node_id(site_id, "area", area.id)
                graph.add_location(
                    SemanticLocation(
                        location_id=area_id,
                        name=area.name,
                        location_type="area",
                        parent_id=site_id,
                        metadata={"source_type": "area", "site_id": site.id},
                    )
                )
                graph.add_entity(
                    SemanticEntity(
                        entity_id=area_id,
                        entity_type="area",
                        name=area.name,
                        labels=("area",),
                        metadata={"source_type": "area", "site_id": site.id},
                    )
                )
                graph.add_relationship(
                    SemanticRelationship(
                        relationship_id=f"{site_id}->contains->{area_id}",
                        source_id=site_id,
                        target_id=area_id,
                        relationship_type="contains",
                        metadata={"layer": "location"},
                    )
                )

                for line in area.lines.values():
                    line_id = cls._node_id(area_id, "line", line.id)
                    graph.add_location(
                        SemanticLocation(
                            location_id=line_id,
                            name=line.name,
                            location_type="line",
                            parent_id=area_id,
                            metadata={"source_type": "line", "site_id": site.id},
                        )
                    )
                    graph.add_entity(
                        SemanticEntity(
                            entity_id=line_id,
                            entity_type="line",
                            name=line.name,
                            labels=("line",),
                            metadata={"source_type": "line", "site_id": site.id, "area_id": area.id},
                        )
                    )
                    graph.add_relationship(
                        SemanticRelationship(
                            relationship_id=f"{area_id}->contains->{line_id}",
                            source_id=area_id,
                            target_id=line_id,
                            relationship_type="contains",
                            metadata={"layer": "location"},
                        )
                    )

                    for cell in line.cells.values():
                        cell_id = cls._node_id(line_id, "cell", cell.id)
                        graph.add_entity(
                            SemanticEntity(
                                entity_id=cell_id,
                                entity_type="cell",
                                name=cell.name,
                                labels=("cell",),
                                metadata={"source_type": "cell", "site_id": site.id, "line_id": line.id},
                            )
                        )
                        graph.add_relationship(
                            SemanticRelationship(
                                relationship_id=f"{line_id}->contains->{cell_id}",
                                source_id=line_id,
                                target_id=cell_id,
                                relationship_type="contains",
                                metadata={"layer": "location"},
                            )
                        )

                        for asset in cell.assets.values():
                            asset_id = cls._node_id(cell_id, "asset", asset.id)
                            graph.add_entity(
                                SemanticEntity(
                                    entity_id=asset_id,
                                    entity_type=asset.type or "asset",
                                    name=asset.name,
                                    labels=(asset.type, "asset") if asset.type else ("asset",),
                                    metadata={
                                        "source_type": "asset",
                                        "source_asset_id": asset.id,
                                        "site_id": site.id,
                                        "line_id": line.id,
                                        "cell_id": cell.id,
                                    },
                                )
                            )
                            graph.add_relationship(
                                SemanticRelationship(
                                    relationship_id=f"{cell_id}->contains->{asset_id}",
                                    source_id=cell_id,
                                    target_id=asset_id,
                                    relationship_type="contains",
                                    metadata={"layer": "asset"},
                                )
                            )

                            for tag in asset.tags.values():
                                measurement_id = cls._node_id(asset_id, "measurement", tag.id)
                                graph.add_measurement(
                                    SemanticMeasurement(
                                        measurement_id=measurement_id,
                                        entity_id=asset_id,
                                        name=tag.name,
                                        unit=tag.unit,
                                        minimum=tag.min,
                                        maximum=tag.max,
                                        warning_low=tag.warning_low,
                                        warning_high=tag.warning_high,
                                        critical_low=tag.critical_low,
                                        critical_high=tag.critical_high,
                                        sampling_rate_hz=tag.sampling_rate_hz,
                                        metadata={
                                            "source_tag_id": tag.id,
                                            "source_asset_id": asset.id,
                                            "site_id": site.id,
                                            "line_id": line.id,
                                        },
                                    )
                                )
                                graph.add_relationship(
                                    SemanticRelationship(
                                        relationship_id=f"{asset_id}->defines_measurement->{measurement_id}",
                                        source_id=asset_id,
                                        target_id=measurement_id,
                                        relationship_type="defines_measurement",
                                        metadata={"layer": "measurement"},
                                    )
                                )

        return graph


def build_semantic_core_catalog() -> dict[str, Any]:
    graph = SemanticGraph.default()
    return {
        "platform_primitives": list(PLATFORM_PRIMITIVES),
        "ontology_packs": [pack.to_dict() for pack in graph.ontology_packs],
        "summary": graph.counts(),
    }


def load_semantic_graph_from_assets(path: Path | str) -> SemanticGraph:
    from services.assets.model import load_hierarchy

    return SemanticGraph.from_asset_hierarchy(load_hierarchy(path), source_uri=str(path))
