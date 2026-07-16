from __future__ import annotations

import asyncio
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
    registry.put(SourceConnection("conn-mqtt", "Sensor MQTT", "mqtt", "plant-a", "mqtt://broker-a:1883", source_id="gateway-a", config={"topic": "plant/a/#"}, mappings=[SourceMapping(source_field="temperature", asset_id="Pump-01", tag="Temperature", unit="c", scale=2.0)], enabled=True, state="enabled"))
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


def test_sparkplug_b_sources_are_dispatched_via_mqtt_runner(tmp_path, monkeypatch):
    import services.edge_ingest.connectors as connectors
    from services.edge_ingest.settings import SourceRuntime

    async def fake_run_mqtt(settings, publisher, stop_event, source=None):
        return None

    monkeypatch.setattr(connectors, "run_mqtt", fake_run_mqtt)
    monkeypatch.setattr(
        Settings,
        "source_connections",
        lambda self: (
            SourceRuntime(
                connection_id="conn-spb",
                source_protocol="sparkplug_b",
                site_id="plant-a",
                endpoint="mqtt://broker:1883",
                source_id="node-a",
                config={"topic": "spBv1.0/group/DDATA/node-a"},
                mappings=(),
            ),
        ),
    )

    async def run() -> None:
        settings = replace(Settings(), enabled_protocols=("mqtt",))
        publisher = object()
        stop_event = asyncio.Event()
        tasks = connectors.build_connector_tasks(settings, publisher, stop_event)  # type: ignore[arg-type]
        assert len(tasks) == 1
        await asyncio.gather(*tasks)

    asyncio.run(run())
