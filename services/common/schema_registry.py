"""Schema Registry for industrial event schemas.

Manages schema versions, validation, and evolution with compatibility
enforcement. The registry keeps schema validation inside application code
(ADR 0002) instead of depending on an external broker-bundled registry, which
fits the open-source "no extra infra required" stance.

Compatibility modes (standard registry semantics):
- BACKWARD: a new schema can read data written with the previous version.
  Safe changes: adding optional fields, widening types. Unsafe: removing a
  required field, changing a field type, or making an optional field required.
- FORWARD: the previous schema can read data written with the new version.
  Unsafe: adding a required field.
- FULL: both backward and forward.
- NONE: no enforcement (for internal bootstrap only).
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKWARD = "backward"
FORWARD = "forward"
FULL = "full"
NONE = "none"
COMPATIBILITY_MODES = {BACKWARD, FORWARD, FULL, NONE}


class IncompatibleSchemaError(ValueError):
    """Raised when a new schema version violates the configured compatibility mode."""


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

    def field_map(self) -> dict[str, dict[str, Any]]:
        return {f["name"]: f for f in self.fields}


class SchemaRegistry:
    """In-memory schema registry with version history and compatibility checks."""

    def __init__(
        self,
        default_compatibility: str = BACKWARD,
        state_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._schemas: dict[str, list[SchemaVersion]] = {}
        self._compatibility: dict[str, str] = {}
        self._default_compatibility = default_compatibility
        self._state_path = Path(state_path) if state_path else None
        if self._state_path and self._state_path.exists():
            self._load_state()
        else:
            self._register_defaults()
            self._persist_state()

    def _register_defaults(self) -> None:
        # Bootstrap the base schemas. Each is the first version for its subject,
        # so compatibility is not enforced yet (no prior version to compare).
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

    def set_compatibility(self, schema_id: str, mode: str) -> None:
        if mode not in COMPATIBILITY_MODES:
            raise ValueError(f"unknown compatibility mode: {mode}")
        self._compatibility[schema_id] = mode
        self._persist_state()

    def get_compatibility(self, schema_id: str) -> str:
        return self._compatibility.get(schema_id, self._default_compatibility)

    def register(
        self,
        schema_id: str,
        fields: list[dict[str, Any]],
        *,
        compatibility: str | None = None,
        enforce: bool = True,
    ) -> SchemaVersion:
        """Register a new schema version.

        When a prior version exists and ``enforce`` is True, the new version is
        checked against the configured compatibility mode. Raises
        :class:`IncompatibleSchemaError` on violation. Pass ``enforce=False``
        for internal bootstrap or forced migrations.
        """
        if compatibility is not None:
            self.set_compatibility(schema_id, compatibility)

        versions = self._schemas.setdefault(schema_id, [])
        if versions and enforce:
            mode = self.get_compatibility(schema_id)
            if mode != NONE:
                errors = self._check_compatibility(versions[-1], fields, mode)
                if errors:
                    raise IncompatibleSchemaError(
                        f"schema '{schema_id}' is not {mode}-compatible with the "
                        f"previous version: {'; '.join(errors)}"
                    )

        version = len(versions) + 1
        sv = SchemaVersion(
            schema_id=schema_id,
            version=version,
            fields=fields,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        versions.append(sv)
        self._persist_state()
        return sv

    @staticmethod
    def _check_compatibility(
        previous: SchemaVersion,
        new_fields: list[dict[str, Any]],
        mode: str,
    ) -> list[str]:
        """Return a list of compatibility violation messages (empty if OK)."""
        prev_map = previous.field_map()
        new_map = {f["name"]: f for f in new_fields}
        errors: list[str] = []

        if mode in (BACKWARD, FULL):
            # New reader must handle old data.
            for name, prev_field in prev_map.items():
                new_field = new_map.get(name)
                if prev_field.get("required") and new_field is None:
                    errors.append(f"removed required field '{name}'")
                elif new_field is not None and new_field.get("type") != prev_field.get("type"):
                    errors.append(
                        f"field '{name}' type changed from "
                        f"'{prev_field.get('type')}' to '{new_field.get('type')}'"
                    )
                elif (
                    new_field is not None
                    and not prev_field.get("required")
                    and new_field.get("required")
                ):
                    errors.append(f"field '{name}' became required")

        if mode in (FORWARD, FULL):
            # Old reader must handle new data.
            for name, new_field in new_map.items():
                if name not in prev_map and new_field.get("required"):
                    errors.append(f"added required field '{name}'")

        return errors

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
                "compatibility": self.get_compatibility(sid),
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_compatibility": self._default_compatibility,
            "compatibility": dict(self._compatibility),
            "schemas": {
                schema_id: [version.to_dict() for version in versions]
                for schema_id, versions in self._schemas.items()
            },
        }

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive bootstrap path
            raise ValueError(f"failed to load schema registry state from {self._state_path}") from exc

        self._default_compatibility = payload.get("default_compatibility", self._default_compatibility)
        self._compatibility = dict(payload.get("compatibility", {}))
        self._schemas = {}
        for schema_id, versions in payload.get("schemas", {}).items():
            self._schemas[schema_id] = [
                SchemaVersion(
                    schema_id=item["schema_id"],
                    version=item["version"],
                    fields=list(item.get("fields", [])),
                    created_at=item.get("created_at", ""),
                )
                for item in versions
            ]

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._state_path)


SCHEMA_REGISTRY_PATH = os.environ.get("SCHEMA_REGISTRY_PATH")

# Global registry
schema_registry = SchemaRegistry(state_path=SCHEMA_REGISTRY_PATH)
