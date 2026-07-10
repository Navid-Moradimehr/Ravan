from __future__ import annotations

import json

import pytest

from services.common.connection_registry import ConnectionRegistry, ConnectionValidationError, SourceConnection, SourceMapping


def _connection(**overrides):
    payload = {
        "connection_id": "conn-pump-01",
        "name": "Pump OPC UA",
        "source_protocol": "opcua",
        "site_id": "plant-a",
        "endpoint": "opc.tcp://10.0.0.5:4840",
        "credential_ref": "secret://plant-a/opcua/pump",
        "config": {"nodes": ["ns=2;s=Pump-01.Temperature"]},
        "mappings": [SourceMapping(source_field="ns=2;s=Pump-01.Temperature", asset_id="Pump-01", tag="Temperature")],
    }
    payload.update(overrides)
    return SourceConnection(**payload)


def test_registry_persists_connections_and_versions(tmp_path):
    path = tmp_path / "connections.json"
    registry = ConnectionRegistry(path)
    registry.put(_connection())
    registry.put(_connection(name="Pump OPC UA v2"))

    reloaded = ConnectionRegistry(path)
    saved = reloaded.get("conn-pump-01")
    assert saved is not None
    assert saved.name == "Pump OPC UA v2"
    assert saved.config_version == 2
    assert json.loads(path.read_text())["contracts"]["secrets_are_references_only"] is True


def test_registry_rejects_secret_material(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    with pytest.raises(ConnectionValidationError, match="password"):
        registry.put(_connection(config={"password": "plain-text"}))


def test_registry_filters_by_site_and_enabled(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(_connection())
    registry.put(_connection(connection_id="conn-mqtt", source_protocol="mqtt", endpoint="mqtt://broker", site_id="plant-b"))
    registry.set_enabled("conn-mqtt", True)

    assert [item.connection_id for item in registry.list(site_id="plant-b", enabled=True)] == ["conn-mqtt"]
    assert registry.list(site_id="plant-a", enabled=True) == []
