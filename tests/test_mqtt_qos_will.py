from __future__ import annotations

import asyncio
import sys
import types

import pytest

from services.edge_ingest.settings import Settings


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    """Stub psycopg2 and confluent_kafka so edge modules import cleanly."""
    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("OperationalError", (Exception,), {})
    psycopg_fake.InterfaceError = type("InterfaceError", (Exception,), {})
    psycopg_fake.Error = type("Error", (Exception,), {})
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda obj: obj
    extras_fake.RealDictCursor = type("RealDictCursor", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type(
        "ThreadedConnectionPool", (), {"__init__": lambda *a, **k: None}
    )
    psycopg_fake.extras = extras_fake
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)

    kafka_fake = types.ModuleType("confluent_kafka")
    kafka_fake.Producer = type("Producer", (), {"__init__": lambda *a, **k: None})
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_fake)


class _RecordingClient:
    """Fake paho client that records subscribe/will_set/connect calls.

    ``connect`` succeeds and immediately drives ``on_connect`` with reason 0 so
    the subscribe path executes without a real broker.
    """

    def __init__(self, *args, **kwargs):
        self.subscribed: list[tuple[str, int]] = []
        self.wills: list[dict] = []
        self.connected = False
        self.loop_started = False
        self.disconnected = False
        self.on_connect = None
        self.on_message = None

    def on_connect_set(self, fn):
        self.on_connect = fn

    def will_set(self, topic, payload=None, qos=1, retain=False):
        self.wills.append({"topic": topic, "payload": payload, "qos": qos, "retain": retain})

    def tls_set(self, *args, **kwargs):
        pass

    def connect(self, host, port, keepalive=60):
        self.connected = True
        # Simulate a successful connect callback so the subscribe path runs.
        if self.on_connect is not None:
            self.on_connect(self, None, {}, 0, None)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.disconnected = True

    def subscribe(self, topic, qos=0):
        self.subscribed.append((topic, qos))


def _make_publisher(monkeypatch):
    from services.edge_ingest import publisher as publisher_mod

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            if on_delivery is not None:
                on_delivery(None, None)

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            return 0

    monkeypatch.setattr(publisher_mod, "Producer", FakeProducer)
    return publisher_mod.EdgePublisher(Settings(max_message_bytes=1048576), batch_size=64)


def test_settings_default_qos_and_disabled_will():
    s = Settings()
    assert s.mqtt_qos == 1
    assert s.mqtt_will_topic == ""
    assert s.mqtt_will_retain is False
    assert s.mqtt_retained_available is True


def test_subscribe_uses_configured_qos(monkeypatch):
    """The subscription is created with the configured QoS level."""
    from services.edge_ingest.connectors import mqtt as mqtt_mod

    monkeypatch.setattr(mqtt_mod.mqtt, "Client", lambda *a, **k: _RecordingClient())

    publisher = _make_publisher(monkeypatch)
    settings = Settings(mqtt_qos=2, mqtt_will_topic="")
    stop = asyncio.Event()

    async def run():
        await mqtt_mod.run_mqtt(settings, publisher, stop)

    # Run briefly then stop; on_connect fires during connect().
    async def drive():
        task = asyncio.create_task(run())
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(drive())

    # The fake client recorded the subscribe call with qos=2.
    # run_mqtt created the client internally; capture it via the patched factory.
    # We re-run with a captured client to inspect subscribe.
    captured: list[_RecordingClient] = []

    def capturing_factory(*a, **k):
        c = _RecordingClient()
        captured.append(c)
        return c

    monkeypatch.setattr(mqtt_mod.mqtt, "Client", capturing_factory)
    stop2 = asyncio.Event()

    async def run2():
        await mqtt_mod.run_mqtt(settings, publisher, stop2)

    async def drive2():
        task = asyncio.create_task(run2())
        await asyncio.sleep(0.1)
        stop2.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(drive2())
    assert captured, "no client was created"
    assert ("factory/+/+/+", 2) in captured[0].subscribed
    assert captured[0].wills == []


def test_last_will_is_configured_when_topic_set(monkeypatch):
    """A will topic enables the LWT on the broker with the supplied options."""
    from services.edge_ingest.connectors import mqtt as mqtt_mod

    captured: list[_RecordingClient] = []

    def factory(*a, **k):
        c = _RecordingClient()
        captured.append(c)
        return c

    monkeypatch.setattr(mqtt_mod.mqtt, "Client", factory)
    publisher = _make_publisher(monkeypatch)
    settings = Settings(
        mqtt_will_topic="factory/edge-ingest/status",
        mqtt_will_payload='{"status":"offline"}',
        mqtt_will_qos=1,
        mqtt_will_retain=True,
    )
    stop = asyncio.Event()

    async def run():
        await mqtt_mod.run_mqtt(settings, publisher, stop)

    async def drive():
        task = asyncio.create_task(run())
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(drive())
    assert captured, "no client was created"
    assert len(captured[0].wills) == 1
    will = captured[0].wills[0]
    assert will["topic"] == "factory/edge-ingest/status"
    assert will["payload"] == b'{"status":"offline"}'
    assert will["qos"] == 1
    assert will["retain"] is True


def test_no_will_configured_by_default(monkeypatch):
    """Without a will topic, will_set is never called."""
    from services.edge_ingest.connectors import mqtt as mqtt_mod

    captured: list[_RecordingClient] = []

    def factory(*a, **k):
        c = _RecordingClient()
        captured.append(c)
        return c

    monkeypatch.setattr(mqtt_mod.mqtt, "Client", factory)
    publisher = _make_publisher(monkeypatch)
    settings = Settings(mqtt_will_topic="")
    stop = asyncio.Event()

    async def run():
        await mqtt_mod.run_mqtt(settings, publisher, stop)

    async def drive():
        task = asyncio.create_task(run())
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(drive())
    assert captured, "no client was created"
    assert captured[0].wills == []


def test_will_payload_none_when_empty(monkeypatch):
    """An empty will payload is sent as None (broker uses a zero-length body)."""
    from services.edge_ingest.connectors import mqtt as mqtt_mod

    captured: list[_RecordingClient] = []

    def factory(*a, **k):
        c = _RecordingClient()
        captured.append(c)
        return c

    monkeypatch.setattr(mqtt_mod.mqtt, "Client", factory)
    publisher = _make_publisher(monkeypatch)
    settings = Settings(mqtt_will_topic="factory/edge-ingest/status", mqtt_will_payload="")
    stop = asyncio.Event()

    async def run():
        await mqtt_mod.run_mqtt(settings, publisher, stop)

    async def drive():
        task = asyncio.create_task(run())
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(drive())
    assert captured, "no client was created"
    assert captured[0].wills[0]["payload"] is None
