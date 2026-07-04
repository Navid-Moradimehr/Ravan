from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from services.common.semantic_core import DEFAULT_ONTOLOGY_PACKS, OntologyPack


@dataclass(frozen=True)
class SemanticField:
    name: str
    expression: str
    kind: str = "dimension"
    searchable: bool = True
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticEntity:
    name: str
    table: str
    ontology_pack: str = "platform.core"
    kind: str = "fact"
    time_field: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    fields: tuple[SemanticField, ...] = field(default_factory=tuple)
    default_limit: int = 100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def field_map(self) -> dict[str, SemanticField]:
        return {field.name: field for field in self.fields}

    def search_index_terms(self) -> set[str]:
        terms = {self.name, self.table, *self.aliases}
        for field in self.fields:
            terms.add(field.name)
            terms.update(field.aliases)
        return {term.lower() for term in terms if term}


@dataclass(frozen=True)
class SemanticModel:
    name: str
    version: str
    ontology_packs: tuple[OntologyPack, ...]
    entities: tuple[SemanticEntity, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def entity_map(self) -> dict[str, SemanticEntity]:
        return {entity.name: entity for entity in self.entities}

    def pack_map(self) -> dict[str, OntologyPack]:
        return {pack.pack_id: pack for pack in self.ontology_packs}

    def find_pack(self, pack_id: str) -> OntologyPack | None:
        lookup = str(pack_id).lower().strip()
        for pack in self.ontology_packs:
            if lookup == pack.pack_id.lower() or lookup == pack.name.lower():
                return pack
        return None

    def infer_pack(self, query_terms: list[str]) -> OntologyPack | None:
        lowered = {term.lower() for term in query_terms}
        best: OntologyPack | None = None
        best_score = -1
        for pack in self.ontology_packs:
            score = 0
            terms = {pack.pack_id.lower(), pack.name.lower(), pack.layer.lower()}
            terms.update(concept.lower() for concept in pack.concepts)
            for note in pack.notes:
                terms.update(note.lower().split())
            for term in lowered:
                if term in terms:
                    score += 3
                elif any(term in candidate or candidate in term for candidate in terms):
                    score += 1
            if score > best_score:
                best = pack
                best_score = score
        return best

    def find_entity(self, name: str) -> SemanticEntity | None:
        lookup = str(name).lower().strip()
        for entity in self.entities:
            if lookup == entity.name.lower() or lookup == entity.table.lower():
                return entity
            if lookup in {alias.lower() for alias in entity.aliases}:
                return entity
        return None

    def infer_entity(self, query_terms: list[str]) -> SemanticEntity:
        lowered = {term.lower() for term in query_terms}
        best: SemanticEntity | None = None
        best_score = -1
        for entity in self.entities:
            score = 0
            terms = entity.search_index_terms()
            for term in lowered:
                if term in terms:
                    score += 3
                elif any(term in candidate or candidate in term for candidate in terms):
                    score += 1
            if score > best_score:
                best = entity
                best_score = score
        if best is None:
            raise ValueError("semantic model has no entities")
        return best


def _default_model_dict() -> dict[str, Any]:
    return {
        "name": "industrial-streaming-semantic-model",
        "version": "1.0",
        "notes": [
            "Semantic layer is deterministic and provider-neutral.",
            "It is designed to compile only validated select queries.",
        ],
        "ontology_packs": list(DEFAULT_ONTOLOGY_PACKS),
        "entities": [
            {
                "name": "industrial_events",
                "table": "industrial_events",
                "ontology_pack": "platform.core",
                "kind": "fact",
                "time_field": "time",
                "aliases": ["events", "historian", "telemetry", "measurements"],
                "fields": [
                    {"name": "time", "expression": "time", "kind": "dimension", "aliases": ["timestamp", "datetime"]},
                    {"name": "asset_id", "expression": "asset_id", "kind": "dimension", "aliases": ["device", "machine", "asset"]},
                    {"name": "tag", "expression": "tag", "kind": "dimension", "aliases": ["signal", "sensor"]},
                    {"name": "site", "expression": "site", "kind": "dimension", "aliases": ["plant"]},
                    {"name": "line", "expression": "line", "kind": "dimension", "aliases": ["area", "production_line"]},
                    {"name": "value", "expression": "value", "kind": "measure"},
                    {"name": "quality", "expression": "quality", "kind": "dimension"},
                    {"name": "fault_type", "expression": "fault_type", "kind": "dimension"},
                    {"name": "ground_truth_severity", "expression": "ground_truth_severity", "kind": "dimension"},
                ],
                "default_limit": 100,
            },
            {
                "name": "processed_events",
                "table": "processed_events",
                "ontology_pack": "platform.core",
                "kind": "fact",
                "time_field": "time",
                "aliases": ["alarms", "warnings", "anomalies"],
                "fields": [
                    {"name": "time", "expression": "time", "kind": "dimension"},
                    {"name": "asset_id", "expression": "asset_id", "kind": "dimension"},
                    {"name": "tag", "expression": "tag", "kind": "dimension"},
                    {"name": "severity", "expression": "severity", "kind": "dimension"},
                    {"name": "window_size", "expression": "window_size", "kind": "measure"},
                    {"name": "anomaly_score", "expression": "anomaly_score", "kind": "measure"},
                    {"name": "evaluation", "expression": "evaluation", "kind": "dimension"},
                ],
                "default_limit": 100,
            },
            {
                "name": "assets",
                "table": "assets",
                "ontology_pack": "industry.manufacturing",
                "kind": "dimension",
                "aliases": ["hierarchy", "site topology", "equipment"],
                "fields": [
                    {"name": "id", "expression": "id", "kind": "dimension"},
                    {"name": "name", "expression": "name", "kind": "dimension"},
                    {"name": "type", "expression": "type", "kind": "dimension"},
                    {"name": "path", "expression": "path", "kind": "dimension"},
                    {"name": "parent_id", "expression": "parent_id", "kind": "dimension"},
                ],
                "default_limit": 500,
            },
            {
                "name": "report_templates",
                "table": "report_templates",
                "ontology_pack": "platform.core",
                "kind": "dimension",
                "aliases": ["reports", "templates"],
                "fields": [
                    {"name": "template_id", "expression": "template_id", "kind": "dimension"},
                    {"name": "name", "expression": "name", "kind": "dimension"},
                    {"name": "description", "expression": "description", "kind": "dimension"},
                    {"name": "format", "expression": "format", "kind": "dimension"},
                ],
                "default_limit": 100,
            },
            {
                "name": "scenarios",
                "table": "scenarios",
                "ontology_pack": "platform.core",
                "kind": "dimension",
                "aliases": ["simulation", "test cases", "benchmarks"],
                "fields": [
                    {"name": "scenario_id", "expression": "scenario_id", "kind": "dimension"},
                    {"name": "name", "expression": "name", "kind": "dimension"},
                    {"name": "description", "expression": "description", "kind": "dimension"},
                    {"name": "category", "expression": "category", "kind": "dimension"},
                ],
                "default_limit": 100,
            },
        ],
    }


def _load_model_from_data(data: dict[str, Any]) -> SemanticModel:
    ontology_packs = tuple(
        OntologyPack(
            pack_id=str(raw_pack.get("pack_id", "")),
            name=str(raw_pack.get("name", "")),
            layer=str(raw_pack.get("layer", "platform")),
            version=str(raw_pack.get("version", "1.0")),
            concepts=tuple(str(concept) for concept in raw_pack.get("concepts", []) if concept),
            notes=tuple(str(note) for note in raw_pack.get("notes", []) if note),
        )
        for raw_pack in data.get("ontology_packs", [])
        if raw_pack.get("pack_id")
    )
    entities: list[SemanticEntity] = []
    for raw_entity in data.get("entities", []):
        fields = tuple(
            SemanticField(
                name=str(raw_field.get("name", "")),
                expression=str(raw_field.get("expression", raw_field.get("name", ""))),
                kind=str(raw_field.get("kind", "dimension")),
                searchable=bool(raw_field.get("searchable", True)),
                aliases=tuple(str(alias) for alias in raw_field.get("aliases", []) if alias),
            )
            for raw_field in raw_entity.get("fields", [])
            if raw_field.get("name")
        )
        entities.append(
            SemanticEntity(
                name=str(raw_entity.get("name", "")),
                table=str(raw_entity.get("table", raw_entity.get("name", ""))),
                ontology_pack=str(raw_entity.get("ontology_pack", "platform.core")),
                kind=str(raw_entity.get("kind", "fact")),
                time_field=raw_entity.get("time_field"),
                aliases=tuple(str(alias) for alias in raw_entity.get("aliases", []) if alias),
                fields=fields,
                default_limit=int(raw_entity.get("default_limit", 100)),
            )
        )
    return SemanticModel(
        name=str(data.get("name", "industrial-semantic-model")),
        version=str(data.get("version", "1.0")),
        ontology_packs=ontology_packs or tuple(
            OntologyPack(
                pack_id=str(raw_pack["pack_id"]),
                name=str(raw_pack["name"]),
                layer=str(raw_pack["layer"]),
                version=str(raw_pack["version"]),
                concepts=tuple(str(concept) for concept in raw_pack["concepts"]),
                notes=tuple(str(note) for note in raw_pack["notes"]),
            )
            for raw_pack in DEFAULT_ONTOLOGY_PACKS
        ),
        entities=tuple(entities),
        notes=tuple(str(note) for note in data.get("notes", []) if note),
    )


@lru_cache(maxsize=8)
def load_semantic_model(path: str | Path | None = None) -> SemanticModel:
    if path is None:
        path = Path("config/semantic-model.yaml")
    path = Path(path)
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = _default_model_dict()
    return _load_model_from_data(data)
