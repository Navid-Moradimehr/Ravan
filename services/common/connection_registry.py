"""Deployment-owned source connection definitions.

The registry describes how an edge source should be connected without owning
the plant secret itself. It is deliberately lightweight and file-backed so a
single Docker Compose deployment does not need another service.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_PROTOCOLS = {"opcua", "mqtt", "modbus", "modbus_rtu", "sparkplug_b", "rest", "file", "dataset", "mock"}
CONNECTION_STATES = {"disabled", "configured", "enabled", "error"}
SECRET_KEY_PATTERN = re.compile(r"(password|passwd|token|secret|private[_-]?key|api[_-]?key)", re.I)


class ConnectionValidationError(ValueError):
    """Raised when a source definition is unsafe or incomplete."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_secret_fields(value: Any, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY_PATTERN.search(str(key)):
                raise ConnectionValidationError(f"{path}.{key} must be a credential reference, not secret material")
            _reject_secret_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_fields(child, f"{path}[{index}]")


@dataclass(frozen=True)
class SourceMapping:
    source_field: str
    asset_id: str
    tag: str
    site_id: str = ""
    line: str = ""
    unit: str = ""
    scale: float = 1.0
    offset: float = 0.0
    quality_field: str = ""
    timestamp_field: str = ""
    value_kind: str = "measurement"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceConnection:
    connection_id: str
    name: str
    source_protocol: str
    site_id: str
    endpoint: str = ""
    source_id: str = ""
    credential_ref: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    mappings: list[SourceMapping] = field(default_factory=list)
    enabled: bool = False
    state: str = "configured"
    config_version: int = 1
    last_error: str = ""
    last_success_at: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.connection_id.strip():
            errors.append("connection_id is required")
        if not self.name.strip():
            errors.append("name is required")
        if self.source_protocol not in SUPPORTED_PROTOCOLS:
            errors.append(f"source_protocol must be one of {sorted(SUPPORTED_PROTOCOLS)}")
        if not self.site_id.strip():
            errors.append("site_id is required")
        if self.source_protocol not in {"dataset", "mock", "file"} and not self.endpoint.strip():
            errors.append("endpoint is required for network sources")
        if self.state not in CONNECTION_STATES:
            errors.append(f"state must be one of {sorted(CONNECTION_STATES)}")
        if self.enabled and self.state == "disabled":
            errors.append("enabled connections cannot have disabled state")
        try:
            _reject_secret_fields(self.config)
        except ConnectionValidationError as exc:
            errors.append(str(exc))
        for index, mapping in enumerate(self.mappings):
            if not mapping.source_field.strip():
                errors.append(f"mappings[{index}].source_field is required")
            if not mapping.asset_id.strip():
                errors.append(f"mappings[{index}].asset_id is required")
            if not mapping.tag.strip():
                errors.append(f"mappings[{index}].tag is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mappings"] = [mapping.to_dict() for mapping in self.mappings]
        return payload


def _mapping_from_dict(payload: dict[str, Any]) -> SourceMapping:
    allowed = {field.name for field in SourceMapping.__dataclass_fields__.values()}
    return SourceMapping(**{key: payload[key] for key in allowed if key in payload})


def connection_from_dict(payload: dict[str, Any]) -> SourceConnection:
    data = dict(payload)
    data.setdefault("connection_id", f"conn-{uuid.uuid4().hex[:12]}")
    data.setdefault("name", data["connection_id"])
    data.setdefault("source_protocol", "mock")
    data.setdefault("site_id", "demo-site")
    data["mappings"] = [_mapping_from_dict(item) for item in data.get("mappings", [])]
    allowed = {field.name for field in SourceConnection.__dataclass_fields__.values()}
    connection = SourceConnection(**{key: data[key] for key in allowed if key in data})
    errors = connection.validate()
    if errors:
        raise ConnectionValidationError("; ".join(errors))
    return connection


class ConnectionRegistry:
    """Small durable registry for deployment-owned connection metadata."""

    def __init__(self, state_path: str | os.PathLike[str] | None = None):
        configured_path = state_path or os.getenv("DATASTREAM_CONNECTION_REGISTRY_PATH")
        self._state_path = Path(configured_path) if configured_path else Path(".datastream/connection-registry.json")
        self._connections: dict[str, SourceConnection] = {}
        if self._state_path.exists():
            self._load()

    def list(self, *, site_id: str | None = None, enabled: bool | None = None) -> list[SourceConnection]:
        values = list(self._connections.values())
        if site_id:
            values = [item for item in values if item.site_id == site_id]
        if enabled is not None:
            values = [item for item in values if item.enabled is enabled]
        return sorted(values, key=lambda item: item.connection_id)

    def get(self, connection_id: str) -> SourceConnection | None:
        return self._connections.get(connection_id)

    def put(self, connection: SourceConnection) -> SourceConnection:
        errors = connection.validate()
        if errors:
            raise ConnectionValidationError("; ".join(errors))
        existing = self._connections.get(connection.connection_id)
        connection.config_version = (existing.config_version + 1) if existing else connection.config_version
        connection.updated_at = _now()
        if existing:
            connection.created_at = existing.created_at
        self._connections[connection.connection_id] = connection
        self._persist()
        return connection

    def delete(self, connection_id: str) -> bool:
        if connection_id not in self._connections:
            return False
        del self._connections[connection_id]
        self._persist()
        return True

    def set_enabled(self, connection_id: str, enabled: bool) -> SourceConnection:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise KeyError(connection_id)
        connection.enabled = enabled
        connection.state = "enabled" if enabled else "disabled"
        connection.updated_at = _now()
        self._persist()
        return connection

    def export(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_at": _now(),
            "connections": [item.to_dict() for item in self.list()],
            "contracts": {
                "secrets_are_references_only": True,
                "runtime_compatible_with_environment_settings": True,
            },
        }

    def _load(self) -> None:
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._connections = {item.connection_id: item for item in (connection_from_dict(raw) for raw in payload.get("connections", []))}

    def _persist(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.export(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)


connection_registry = ConnectionRegistry()
