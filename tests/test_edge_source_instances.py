from __future__ import annotations

from dataclasses import replace

from services.common.connection_registry import ConnectionRegistry, SourceConnection, SourceMapping
from services.edge_ingest.settings import Settings


def test_settings_loads_multiple_enabled_sources_from_registry(tmp_path, monkeypatch):
    path = tmp_path / "connections.json"
    registry = ConnectionRegistry(path)
    registry.put(SourceConnection("conn-opcua", "Pump OPC UA", "opcua", "plant-a", "opc.tcp://opcua-a:4840", config={"nodes": ["n1"]}, enabled=True, state="enabled"))
    registry.put(SourceConnection("conn-mqtt", "Sensor MQTT", "mqtt", "plant-a", "mqtt://broker-a:1883", config={"topic": "plant/a/#"}, enabled=True, state="enabled"))
    monkeypatch.setenv("DATASTREAM_CONNECTION_REGISTRY_PATH", str(path))

    sources = Settings().source_connections()

    assert [source.connection_id for source in sources] == ["conn-mqtt", "conn-opcua"]
    assert sources[0].options["topic"] == "plant/a/#"


def test_registry_mapping_is_applied_before_validation(tmp_path, monkeypatch):
    path = tmp_path / "connections.json"
    registry = ConnectionRegistry(path)
    registry.put(SourceConnection("conn-mqtt", "Sensor MQTT", "mqtt", "plant-a", "mqtt://broker-a:1883", source_id="gateway-a", mappings=[SourceMapping(source_field="temperature", asset_id="Pump-01", tag="Temperature", unit="c", scale=2.0)], enabled=True, state="enabled"))
    monkeypatch.setenv("DATASTREAM_CONNECTION_REGISTRY_PATH", str(path))

    source = Settings().source_connections()[0]
    mapped = source.map_event({"tag": "temperature", "value": 20})
    assert mapped["asset_id"] == "Pump-01"
    assert mapped["tag"] == "Temperature"
    assert mapped["value"] == 40.0


def test_settings_keeps_legacy_environment_fallback(monkeypatch):
    monkeypatch.setenv("DATASTREAM_CONNECTION_REGISTRY_PATH", "missing-connections.json")
    monkeypatch.setenv("EDGE_PROTOCOLS", "mqtt,opcua")
    settings = replace(Settings(), enabled_protocols=("mqtt", "opcua"))

    assert {source.connection_id for source in settings.source_connections()} == {"legacy-mqtt", "legacy-opcua"}
