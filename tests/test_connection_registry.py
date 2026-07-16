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
    registry.put(_connection(connection_id="conn-mqtt", source_protocol="mqtt", endpoint="mqtt://broker", site_id="plant-b", config={"topic": "plant/a/#"}))
    registry.set_enabled("conn-mqtt", True)

    assert [item.connection_id for item in registry.list(site_id="plant-b", enabled=True)] == ["conn-mqtt"]
    assert registry.list(site_id="plant-a", enabled=True) == []


def test_registry_labels_rest_as_runtime_protocol(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    connection = _connection(connection_id="conn-rest", source_protocol="rest", endpoint="https://example.test/api", config={"url": "https://example.test/api"})
    saved = registry.put(connection)

    assert saved.runtime_supported is True
    assert "runtime" in saved.runtime_note
    assert registry.get("conn-rest").to_dict()["runtime_supported"] is True


def test_incomplete_sources_are_saved_as_drafts_but_not_activation_ready(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    saved = registry.put(SourceConnection("rest-draft", "External API", "rest", "plant-a"))
    assert saved.state == "configured"
    assert saved.activation_ready is False
    assert "endpoint" in " ".join(saved.activation_errors())


def test_http_push_has_generated_activation_contract(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    saved = registry.put(SourceConnection("push-1", "Gateway", "http_push", "plant-a"))
    registry.set_enabled("push-1", True)
    assert saved.capabilities == ("push", "batch", "idempotency", "canonical_ingest")


def test_registry_retire_preserves_history_and_hides_from_active_list(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(_connection())

    retired = registry.retire("conn-pump-01", reason="sensor replaced")

    assert retired.state == "retired"
    assert retired.enabled is False
    assert retired.retired_reason == "sensor replaced"
    assert retired.retired_at is not None
    assert registry.list(enabled=True) == []
    assert registry.list(include_retired=False) == []
    assert registry.get("conn-pump-01").state == "retired"


def test_registry_edit_preserves_enabled_state(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(_connection())
    registry.set_enabled("conn-pump-01", True)

    updated = registry.put(_connection(name="Pump OPC UA v2"))

    assert updated.enabled is True
    assert updated.state == "enabled"
    assert updated.config_version == 2


def test_registry_restore_returns_connection_to_configured_state(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(_connection())
    registry.retire("conn-pump-01")

    restored = registry.restore("conn-pump-01")

    assert restored.state == "configured"
    assert restored.enabled is False
    assert restored.retired_at is None


def test_registry_persists_credential_references_without_secret_values(tmp_path):
    registry = ConnectionRegistry(tmp_path / "connections.json")
    saved = registry.put(SourceConnection("mqtt-auth", "Authenticated MQTT", "mqtt", "plant-a", "mqtt://broker:1883", credential_refs={"username": "env://MQTT_USER", "password": "file://C:/secrets/mqtt-password"}))
    loaded = ConnectionRegistry(tmp_path / "connections.json").get(saved.connection_id)
    assert loaded is not None
    assert loaded.credential_refs == {"username": "env://MQTT_USER", "password": "file://C:/secrets/mqtt-password"}
