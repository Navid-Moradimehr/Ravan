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
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_PROTOCOLS = {
    "opcua", "mqtt", "modbus", "modbus_rtu", "sparkplug_b", "rest", "http_push",
    "file", "dataset", "mock",
}
RUNTIME_PROTOCOLS = {"opcua", "mqtt", "modbus", "modbus_rtu", "sparkplug_b", "rest", "http_push"}
METADATA_ONLY_PROTOCOLS = {"file", "dataset", "mock"}
CONNECTION_STATES = {"draft", "disabled", "configured", "validated", "enabled", "error", "retired"}
SECRET_KEY_PATTERN = re.compile(r"(password|passwd|token|secret|private[_-]?key|api[_-]?key)", re.I)

PROTOCOL_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "opcua": ("browse", "read", "subscribe", "credentials", "reconnect"),
    "mqtt": ("subscribe", "qos", "retained_messages", "credentials", "reconnect"),
    "sparkplug_b": ("subscribe", "birth_death", "metrics", "credentials", "reconnect"),
    "modbus": ("read_holding_registers", "scaling", "byte_word_order", "reconnect"),
    "modbus_rtu": ("serial_read", "scaling", "byte_word_order", "reconnect"),
    "rest": ("poll", "json_mapping", "pagination", "conditional_requests", "retries"),
    "http_push": ("push", "batch", "idempotency", "canonical_ingest"),
    "file": ("metadata_reference",),
    "dataset": ("metadata_reference",),
    "mock": ("metadata_reference",),
}
MODBUS_DATA_TYPES = {"uint16", "int16", "bool", "uint32", "int32", "float32", "uint64", "int64", "float64"}
MODBUS_BYTE_ORDERS = {"big", "little"}
MODBUS_WORD_ORDERS = {"big", "little"}
OPCUA_SECURITY_MODES = {"None", "Sign", "SignAndEncrypt"}


class ConnectionValidationError(ValueError):
    """Raised when a source definition is unsafe or incomplete."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_secret_fields(value: Any, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            # A configuration may contain a pointer such as ``token_ref`` or
            # ``api_key_ref``. The value is still checked as a reference below;
            # only secret material itself is prohibited in the registry.
            is_reference_key = key_text.endswith(("_ref", "_refs")) or key_text in {"credential_ref", "credential_refs"}
            if SECRET_KEY_PATTERN.search(key_text) and not is_reference_key:
                raise ConnectionValidationError(f"{path}.{key} must be a credential reference, not secret material")
            _reject_secret_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_fields(child, f"{path}[{index}]")


def _validate_reference(value: Any, path: str) -> list[str]:
    if not str(value or "").strip():
        return [f"{path} must be a non-empty credential reference"]
    if not str(value).startswith(("env://", "file://", "path://", "secret://")):
        return [f"{path} must use env://, file://, path://, or secret://"]
    return []


def _validate_config_references(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    auth = config.get("auth", {}) if isinstance(config, dict) else {}
    if not isinstance(auth, dict):
        return ["config.auth must be an object"]
    auth_type = str(auth.get("type", "none")).lower()
    if auth_type not in {"none", "basic", "bearer", "api_key", "oauth2_client_credentials", "mtls"}:
        errors.append("config.auth.type is unsupported")
        return errors
    required = {
        "basic": ("username_ref", "password_ref"),
        "bearer": ("token_ref",),
        "api_key": ("key_ref",),
        "oauth2_client_credentials": ("client_id_ref", "client_secret_ref"),
        "mtls": ("client_cert_ref", "client_key_ref"),
    }.get(auth_type, ())
    for key in required:
        errors.extend(_validate_reference(auth.get(key), f"config.auth.{key}"))
    if auth_type == "oauth2_client_credentials":
        if not str(auth.get("token_url", "")).startswith(("http://", "https://")):
            errors.append("config.auth.token_url is required for OAuth2 client credentials")
    return errors


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
    credential_refs: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    mappings: list[SourceMapping] = field(default_factory=list)
    enabled: bool = False
    state: str = "configured"
    config_version: int = 1
    last_error: str = ""
    last_success_at: str | None = None
    retired_at: str | None = None
    retired_reason: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def validate_draft(self) -> list[str]:
        """Validate a persistable draft without requiring activation fields."""
        errors: list[str] = []
        if not self.connection_id.strip():
            errors.append("connection_id is required")
        if not self.name.strip():
            errors.append("name is required")
        if self.source_protocol not in SUPPORTED_PROTOCOLS:
            errors.append(f"source_protocol must be one of {sorted(SUPPORTED_PROTOCOLS)}")
        if not self.site_id.strip():
            errors.append("site_id is required")
        if self.state not in CONNECTION_STATES:
            errors.append(f"state must be one of {sorted(CONNECTION_STATES)}")
        if self.enabled and self.state != "enabled":
            errors.append("enabled connections must have enabled state")
        if self.state == "enabled" and not self.enabled:
            errors.append("state enabled requires enabled=true")
        if self.state == "retired" and self.enabled:
            errors.append("retired connections cannot be enabled")
        try:
            _reject_secret_fields(self.config)
        except ConnectionValidationError as exc:
            errors.append(str(exc))
        for key, reference in self.credential_refs.items():
            if not str(key).strip():
                errors.append("credential_refs keys must not be empty")
            if not str(reference).strip():
                errors.append(f"credential_refs.{key} must be a non-empty reference")
            elif not str(reference).startswith(("env://", "file://", "path://", "secret://")):
                errors.append(f"credential_refs.{key} must use env://, file://, path://, or secret://")
        for index, mapping in enumerate(self.mappings):
            if not mapping.source_field.strip():
                errors.append(f"mappings[{index}].source_field is required")
            if not mapping.asset_id.strip():
                errors.append(f"mappings[{index}].asset_id is required")
            if not mapping.tag.strip():
                errors.append(f"mappings[{index}].tag is required")
        return errors

    def activation_errors(self) -> list[str]:
        """Return errors that would make an enabled connector unsafe or inert."""
        errors = self.validate_draft()
        if errors:
            return errors
        protocol = self.source_protocol
        if protocol in {"opcua", "mqtt", "sparkplug_b", "modbus", "rest"} and not self.endpoint.strip():
            errors.append("endpoint is required for this protocol")
        if protocol == "http_push":
            # The listener is owned by the platform; an endpoint is generated
            # after activation and therefore is intentionally not required.
            pass
        if protocol == "opcua":
            nodes = self.config.get("nodes") if isinstance(self.config, dict) else None
            if not nodes and not self.mappings:
                errors.append("OPC UA requires config.nodes or at least one mapping after discovery")
        if protocol in {"mqtt", "sparkplug_b"}:
            if not str(self.config.get("topic", "")).strip():
                errors.append("MQTT requires config.topic before activation")
        if protocol == "sparkplug_b" and bool(self.config.get("request_rebirth_on_connect", False)):
            if not str(self.config.get("group_id", "")).strip():
                errors.append("Sparkplug rebirth requires config.group_id")
            if not str(self.config.get("edge_node_id", "")).strip():
                errors.append("Sparkplug rebirth requires config.edge_node_id")
        if protocol in {"modbus", "modbus_rtu"}:
            registers = self.config.get("registers") if isinstance(self.config, dict) else None
            if not isinstance(registers, list) or not registers:
                errors.append(f"{protocol} requires an explicit config.registers map; demo registers are not used for registry sources")
            else:
                for index, register in enumerate(registers):
                    if not isinstance(register, dict):
                        if protocol == "modbus_rtu" and isinstance(register, str) and ":" in register:
                            continue
                        errors.append(f"{protocol} config.registers[{index}] must be an object")
                        continue
                    data_type = str(register.get("data_type", "uint16")).lower()
                    if data_type not in MODBUS_DATA_TYPES:
                        errors.append(f"Modbus registers[{index}].data_type must be one of {sorted(MODBUS_DATA_TYPES)}")
                    byte_order = str(register.get("byte_order", "big")).lower()
                    word_order = str(register.get("word_order", "big")).lower()
                    if byte_order not in MODBUS_BYTE_ORDERS:
                        errors.append(f"Modbus registers[{index}].byte_order must be big or little")
                    if word_order not in MODBUS_WORD_ORDERS:
                        errors.append(f"Modbus registers[{index}].word_order must be big or little")
        if protocol == "modbus_rtu":
            if not str(self.config.get("port", "")).strip():
                errors.append("Modbus RTU requires config.port")
            registers = self.config.get("registers")
            if not registers:
                errors.append("Modbus RTU requires an explicit config.registers map")
        if protocol == "rest":
            url = str(self.config.get("url") or self.endpoint).strip()
            if not url.startswith(("http://", "https://")):
                errors.append("REST requires an http:// or https:// endpoint")
            method = str(self.config.get("method", "GET")).upper()
            if method not in {"GET", "POST"}:
                errors.append("REST config.method must be GET or POST")
            interval = self.config.get("poll_interval_seconds", 60)
            try:
                if not 1 <= float(interval) <= 86400:
                    errors.append("REST poll_interval_seconds must be between 1 and 86400")
            except (TypeError, ValueError):
                errors.append("REST poll_interval_seconds must be numeric")
            field_paths = self.config.get("response", {}).get("field_paths", {}) if isinstance(self.config.get("response", {}), dict) else {}
            for field in ("value", "asset_id", "tag"):
                if not str(field_paths.get(field, "")).strip():
                    errors.append(f"REST response.field_paths.{field} is required")
        if protocol in {"rest", "http_push"}:
            errors.extend(_validate_config_references(self.config))
        if protocol == "opcua":
            security = self.config.get("security", {}) if isinstance(self.config.get("security", {}), dict) else {}
            mode = str(security.get("mode", "None"))
            if mode not in OPCUA_SECURITY_MODES:
                errors.append(f"OPC UA security.mode must be one of {sorted(OPCUA_SECURITY_MODES)}")
            if mode != "None" and not str(security.get("policy", "")).strip():
                errors.append("OPC UA security.policy is required when security.mode is not None")
            browse_nodes = self.config.get("browse_nodes", [])
            if browse_nodes and not isinstance(browse_nodes, list):
                errors.append("OPC UA config.browse_nodes must be a list")
        return errors

    def validate(self) -> list[str]:
        """Backward-compatible strict validation used by activation/tests."""
        return self.activation_errors()

    @property
    def activation_ready(self) -> bool:
        return not self.activation_errors()

    @property
    def capabilities(self) -> tuple[str, ...]:
        return PROTOCOL_CAPABILITIES.get(self.source_protocol, ())

    @property
    def runtime_supported(self) -> bool:
        return self.source_protocol in RUNTIME_PROTOCOLS and self.state != "retired"

    @property
    def runtime_note(self) -> str:
        if self.state == "retired":
            return "retired; preserved for audit and replacement history"
        if self.runtime_supported:
            return "runtime-capable"
        if self.source_protocol in METADATA_ONLY_PROTOCOLS:
            return "metadata-only; configure it through the relevant dataset or integration workflow"
        return "unknown protocol"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mappings"] = [mapping.to_dict() for mapping in self.mappings]
        payload["runtime_supported"] = self.runtime_supported
        payload["runtime_note"] = self.runtime_note
        payload["activation_ready"] = self.activation_ready
        payload["activation_errors"] = self.activation_errors()
        payload["capabilities"] = list(self.capabilities)
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
    errors = connection.validate_draft()
    if connection.enabled or connection.state == "enabled":
        errors.extend(connection.activation_errors())
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

    def list(self, *, site_id: str | None = None, enabled: bool | None = None, include_retired: bool = True) -> list[SourceConnection]:
        values = list(self._connections.values())
        if not include_retired:
            values = [item for item in values if item.state != "retired"]
        if site_id:
            values = [item for item in values if item.site_id == site_id]
        if enabled is not None:
            values = [item for item in values if item.enabled is enabled]
        return sorted(values, key=lambda item: item.connection_id)

    def get(self, connection_id: str) -> SourceConnection | None:
        return self._connections.get(connection_id)

    def put(self, connection: SourceConnection) -> SourceConnection:
        errors = connection.validate_draft()
        if connection.enabled or connection.state == "enabled":
            errors.extend(connection.activation_errors())
        if errors:
            raise ConnectionValidationError("; ".join(errors))
        existing = self._connections.get(connection.connection_id)
        connection.config_version = (existing.config_version + 1) if existing else connection.config_version
        connection.updated_at = _now()
        if existing:
            connection.created_at = existing.created_at
            connection.last_error = existing.last_error
            connection.last_success_at = existing.last_success_at
            if existing.state == "retired":
                connection.state = "retired"
                connection.enabled = False
                connection.retired_at = existing.retired_at or _now()
                connection.retired_reason = existing.retired_reason
            else:
                connection.enabled = existing.enabled
                connection.state = existing.state
                connection.retired_at = existing.retired_at
                connection.retired_reason = existing.retired_reason
        self._connections[connection.connection_id] = connection
        self._persist()
        return connection

    def retire(self, connection_id: str, reason: str = "retired by operator") -> SourceConnection:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise KeyError(connection_id)
        connection.enabled = False
        connection.state = "retired"
        connection.retired_at = _now()
        connection.retired_reason = reason
        connection.updated_at = _now()
        self._persist()
        return connection

    def restore(self, connection_id: str) -> SourceConnection:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise KeyError(connection_id)
        connection.state = "configured"
        connection.enabled = False
        connection.retired_at = None
        connection.retired_reason = ""
        connection.updated_at = _now()
        self._persist()
        return connection

    def delete(self, connection_id: str) -> bool:
        if connection_id not in self._connections:
            return False
        self.retire(connection_id)
        return True

    def set_enabled(self, connection_id: str, enabled: bool) -> SourceConnection:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise KeyError(connection_id)
        if connection.state == "retired":
            raise ConnectionValidationError("retired connections must be restored before they can be enabled")
        if enabled:
            errors = connection.activation_errors()
            if errors:
                raise ConnectionValidationError("; ".join(errors))
        connection.enabled = enabled
        connection.state = "enabled" if enabled else "disabled"
        connection.updated_at = _now()
        self._persist()
        return connection

    def save_opcua_browse_selection(self, connection_id: str, node_ids: list[str]) -> SourceConnection:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise KeyError(connection_id)
        if connection.source_protocol != "opcua":
            raise ConnectionValidationError("browse selections are supported only for OPC UA connections")
        selected = list(dict.fromkeys(str(node_id).strip() for node_id in node_ids if str(node_id).strip()))
        if not selected:
            raise ConnectionValidationError("at least one OPC UA node ID is required")
        if len(selected) > 500:
            raise ConnectionValidationError("at most 500 OPC UA browse selections may be saved")
        config = dict(connection.config)
        config["nodes"] = selected
        config["browse_nodes"] = selected
        updated = replace(connection, config=config)
        return self.put(updated)

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
