from __future__ import annotations

import json

import pytest

from services.common.sink_routing import SinkRoute, SinkRouteRegistry


def test_sink_route_registry_persists_enabled_types(tmp_path):
    path = tmp_path / "sink-routes.json"
    registry = SinkRouteRegistry(path)
    registry.put(SinkRoute(route_id="historian-main", name="Hot historian", sink_type="historian"))
    registry.put(SinkRoute(route_id="lakehouse-off", name="Cold archive", sink_type="lakehouse", enabled=False))

    restored = SinkRouteRegistry(path)
    assert restored.enabled_sink_types() == ["historian"]
    assert json.loads(path.read_text()) ["contracts"]["secrets_are_references_only"] is True


def test_sink_route_registry_rejects_secret_material(tmp_path):
    registry = SinkRouteRegistry(tmp_path / "routes.json")
    with pytest.raises(ValueError, match="credential reference"):
        registry.put(SinkRoute(
            route_id="bad",
            name="Bad",
            sink_type="kafka",
            config={"password": "do-not-store"},
        ))


def test_sink_registry_prefers_persisted_routes_when_sinks_unset(tmp_path, monkeypatch):
    from services.sinks.base import SinkRegistry

    registry = SinkRouteRegistry(tmp_path / "routes.json")
    registry.put(SinkRoute(route_id="disabled", name="Disabled", sink_type="historian", enabled=False))
    monkeypatch.setattr(SinkRegistry, "_build", staticmethod(lambda name, env: name))
    composite = SinkRegistry.from_env({"DATASTREAM_SINK_ROUTING_PATH": str(tmp_path / "routes.json")})
    assert composite.sinks == []


def test_sink_registry_keeps_environment_compatibility(monkeypatch):
    from services.sinks.base import SinkRegistry

    monkeypatch.setattr(SinkRegistry, "_build", staticmethod(lambda name, env: name))
    composite = SinkRegistry.from_env({"SINKS": "historian,kafka"})
    assert composite.sinks == ["historian", "kafka"]
