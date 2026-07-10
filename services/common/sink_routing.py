"""Deployment-owned sink route metadata.

This is intentionally a small file-backed control-plane contract.  The
fan-out runtime still accepts ``SINKS`` for backwards compatibility, while
deployments that use the API can persist which supported sink types are
enabled.  Credentials remain outside this registry and are referenced by
name only.
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

SUPPORTED_SINK_TYPES = {"historian", "kafka", "lakehouse"}
_SECRET_KEY = re.compile(r"(password|passwd|token|secret|private[_-]?key|api[_-]?key)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_secrets(value: Any, path: str = "config") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_KEY.search(str(key)):
                raise ValueError(f"{path}.{key} must be a credential reference, not secret material")
            _reject_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secrets(child, f"{path}[{index}]")


@dataclass
class SinkRoute:
    route_id: str
    name: str
    sink_type: str
    enabled: bool = True
    topic: str = ""
    credential_ref: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.route_id.strip():
            errors.append("route_id is required")
        if not self.name.strip():
            errors.append("name is required")
        if self.sink_type not in SUPPORTED_SINK_TYPES:
            errors.append(f"sink_type must be one of {sorted(SUPPORTED_SINK_TYPES)}")
        try:
            _reject_secrets(self.config)
        except ValueError as exc:
            errors.append(str(exc))
        return errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def route_from_dict(payload: dict[str, Any]) -> SinkRoute:
    data = dict(payload)
    data.setdefault("route_id", f"sink-{uuid.uuid4().hex[:12]}")
    data.setdefault("name", data["route_id"])
    data.setdefault("sink_type", "historian")
    allowed = {field.name for field in SinkRoute.__dataclass_fields__.values()}
    route = SinkRoute(**{key: data[key] for key in allowed if key in data})
    errors = route.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return route


class SinkRouteRegistry:
    def __init__(self, state_path: str | os.PathLike[str] | None = None):
        configured = state_path or os.getenv("DATASTREAM_SINK_ROUTING_PATH")
        self._state_path = Path(configured) if configured else Path(".datastream/sink-routes.json")
        self._routes: dict[str, SinkRoute] = {}
        if self._state_path.exists():
            self._load()

    def list(self, *, enabled: bool | None = None) -> list[SinkRoute]:
        routes = list(self._routes.values())
        if enabled is not None:
            routes = [route for route in routes if route.enabled is enabled]
        return sorted(routes, key=lambda route: route.route_id)

    def get(self, route_id: str) -> SinkRoute | None:
        return self._routes.get(route_id)

    def put(self, route: SinkRoute) -> SinkRoute:
        errors = route.validate()
        if errors:
            raise ValueError("; ".join(errors))
        existing = self._routes.get(route.route_id)
        if existing:
            route.created_at = existing.created_at
        route.updated_at = _now()
        self._routes[route.route_id] = route
        self._persist()
        return route

    def delete(self, route_id: str) -> bool:
        if route_id not in self._routes:
            return False
        del self._routes[route_id]
        self._persist()
        return True

    def export(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_at": _now(),
            "routes": [route.to_dict() for route in self.list()],
            "contracts": {"secrets_are_references_only": True, "runtime_reads_at_startup": True},
        }

    def enabled_sink_types(self) -> list[str]:
        return list(dict.fromkeys(route.sink_type for route in self.list(enabled=True)))

    def _load(self) -> None:
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._routes = {route.route_id: route for route in (route_from_dict(raw) for raw in payload.get("routes", []))}

    def _persist(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.export(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)


sink_route_registry = SinkRouteRegistry()
