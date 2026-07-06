"""Schema Registry for industrial event schemas.

Manages schema versions, validation, and evolution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaVersion:
    schema_id: str
    version: int
    fields: list[dict[str, Any]]
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "version": self.version,
            "fields": self.fields,
            "created_at": self.created_at,
        }


class SchemaRegistry:
    """In-memory schema registry with version history."""

    def __init__(self):
        self._schemas: dict[str, list[SchemaVersion]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("industrial_event", [
            {"name": "event_id", "type": "string", "required": True},
            {"name": "source_protocol", "type": "string", "required": True},
            {"name": "asset_id", "type": "string", "required": True},
            {"name": "tag", "type": "string", "required": True},
            {"name": "value", "type": "float", "required": True},
            {"name": "quality", "type": "string", "required": True},
            {"name": "unit", "type": "string", "required": False},
            {"name": "ts_source", "type": "datetime", "required": True},
        ])
        self.register("processed_event", [
            {"name": "event_id", "type": "string", "required": True},
            {"name": "device_id", "type": "string", "required": True},
            {"name": "asset_id", "type": "string", "required": True},
            {"name": "tag", "type": "string", "required": True},
            {"name": "value", "type": "float", "required": True},
            {"name": "anomaly_score", "type": "float", "required": True},
            {"name": "severity", "type": "string", "required": True},
            {"name": "window_size", "type": "int", "required": True},
            {"name": "timestamp", "type": "datetime", "required": True},
        ])
        # Benchmark metadata is governed separately from the operational event
        # schema so it does not leak into production validation. These optional
        # fields ride along on the event dict but are not required for an
        # industrial event to be valid.
        self.register("benchmark_event", [
            {"name": "event_id", "type": "string", "required": True},
            {"name": "fault_type", "type": "string", "required": False},
            {"name": "scenario_id", "type": "string", "required": False},
            {"name": "ground_truth_severity", "type": "string", "required": False},
            {"name": "step", "type": "int", "required": False},
        ])

    def register(self, schema_id: str, fields: list[dict[str, Any]]) -> SchemaVersion:
        import datetime
        versions = self._schemas.setdefault(schema_id, [])
        version = len(versions) + 1
        sv = SchemaVersion(
            schema_id=schema_id,
            version=version,
            fields=fields,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        versions.append(sv)
        return sv

    def get(self, schema_id: str, version: int | None = None) -> SchemaVersion | None:
        versions = self._schemas.get(schema_id)
        if not versions:
            return None
        if version is None:
            return versions[-1]
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "schema_id": sid,
                "latest_version": versions[-1].version if versions else 0,
                "versions": [v.to_dict() for v in versions],
            }
            for sid, versions in self._schemas.items()
        ]

    def validate(self, schema_id: str, data: dict[str, Any], version: int | None = None) -> dict[str, Any]:
        sv = self.get(schema_id, version)
        if not sv:
            return {"valid": False, "errors": ["Schema not found"]}
        errors = []
        for field in sv.fields:
            name = field["name"]
            required = field.get("required", False)
            if required and name not in data:
                errors.append(f"Missing required field: {name}")
        return {"valid": len(errors) == 0, "errors": errors}


# Global registry
schema_registry = SchemaRegistry()
