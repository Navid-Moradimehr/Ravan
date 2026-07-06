from __future__ import annotations

import asyncio
import sys
import types

import pytest

from services.edge_ingest.model import utc_now
from services.edge_ingest.settings import Settings


@pytest.fixture(autouse=True)
def _stub_psycopg2(monkeypatch):
    """Stub psycopg2 so the historian client imports without the native DLL.

    The Windows venv ships a psycopg2 wheel whose native _psycopg module fails
    to load in some environments; stubbing it lets the historian client module
    import cleanly for unit tests that never touch a real database.
    """
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


def _make_publisher(monkeypatch, producer_cls):
    """Import the publisher once and swap its Producer class before construction."""
    from services.edge_ingest import publisher as publisher_mod

    monkeypatch.setattr(publisher_mod, "Producer", producer_cls)
    monkeypatch.setattr(publisher_mod, "insert_industrial_event", lambda e: None)
    monkeypatch.setattr(publisher_mod, "insert_industrial_events", lambda events: None)
    return publisher_mod, publisher_mod.EdgePublisher(Settings(max_message_bytes=1048576), batch_size=64)


def test_buffer_error_triggers_poll_then_retry(monkeypatch):
    """A BufferError should drain the producer queue and retry, not crash."""
    calls = {"n": 0}

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise BufferError("queue full")
            if on_delivery is not None:
                on_delivery(None, None)

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            return 0

    _mod, publisher = _make_publisher(monkeypatch, FakeProducer)

    publisher.publish_event(
        {
            "source_protocol": "mqtt",
            "source_id": "factory/line-01/Pump-01/Temperature",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 51.2,
            "quality": "good",
            "ts_source": utc_now(),
        }
    )
    publisher.flush()

    assert calls["n"] >= 2  # first raised, second succeeded


def test_oversize_message_routed_to_dlq(monkeypatch):
    """Messages exceeding max_message_bytes are routed to the DLQ, not dropped."""
    produced: list[tuple[str, bytes, bytes]] = []

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            produced.append((topic, key, value))
            if on_delivery is not None:
                on_delivery(None, None)

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            return 0

    from services.edge_ingest import publisher as publisher_mod

    monkeypatch.setattr(publisher_mod, "Producer", FakeProducer)
    publisher = publisher_mod.EdgePublisher(Settings(max_message_bytes=128), batch_size=64)

    big_payload = {
        "source_protocol": "mqtt",
        "source_id": "factory/line-01/Pump-01/Temperature",
        "asset_id": "Pump-01",
        "tag": "Temperature",
        "value": 51.2,
        "quality": "good",
        "ts_source": utc_now(),
        "noise": "x" * 1024,
    }

    publisher.publish_raw("mqtt", "factory/line-01/Pump-01/Temperature", big_payload)
    publisher.flush()

    topics = {p[0] for p in produced}
    assert "industrial.dlq" in topics
    assert "industrial.raw" not in topics


def test_delivery_failure_counter_incremented(monkeypatch):
    """A delivery report error increments the delivery_failures counter."""
    produced: list[tuple] = []

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            produced.append((topic, key, value, on_delivery))

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            return 0

    _mod, publisher = _make_publisher(monkeypatch, FakeProducer)

    publisher.publish_event(
        {
            "source_protocol": "mqtt",
            "source_id": "factory/line-01/Pump-01/Temperature",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 51.2,
            "quality": "good",
            "ts_source": utc_now(),
        }
    )

    class _Err:
        def str(self):
            return "simulated failure"

    class _Msg:
        def topic(self):
            return "industrial.normalized"

    for _topic, _key, _value, on_delivery in produced:
        if on_delivery is not None:
            on_delivery(_Err(), _Msg())

    assert _mod.delivery_failures.labels(topic="industrial.normalized")._value.get() >= 1


def test_mqtt_queue_full_routes_to_dlq(monkeypatch):
    """When the MQTT decoupling queue is saturated, the message goes to the DLQ."""
    produced: list[tuple[str, bytes, bytes]] = []

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            produced.append((topic, key, value))
            if on_delivery is not None:
                on_delivery(None, None)

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            return 0

    _mod, publisher = _make_publisher(monkeypatch, FakeProducer)
    from services.edge_ingest.connectors import mqtt as mqtt_mod

    async def run():
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        queue.put_nowait({"source_protocol": "mqtt", "source_id": "filler", "value": 0})
        overflow_before = _mod.overflow_total.labels(reason="mqtt_queue_full")._value.get()

        payload = {
            "source_protocol": "mqtt",
            "source_id": "factory/line-01/Pump-01/Temperature",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 51.2,
            "quality": "good",
            "ts_source": utc_now(),
        }
        mqtt_mod.enqueue_mqtt_message(
            queue, payload, publisher, "factory/line-01/Pump-01/Temperature"
        )

        assert queue.qsize() == 1
        overflow_after = _mod.overflow_total.labels(reason="mqtt_queue_full")._value.get()
        assert overflow_after > overflow_before

    asyncio.run(run())
    publisher.flush()

    topics = {p[0] for p in produced}
    assert "industrial.dlq" in topics


def test_mqtt_queue_accepts_message_under_capacity(monkeypatch):
    """A message is enqueued (not DLQ'd) when the queue has capacity."""
    produced: list[tuple[str, bytes, bytes]] = []

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            produced.append((topic, key, value))
            if on_delivery is not None:
                on_delivery(None, None)

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            return 0

    _mod, publisher = _make_publisher(monkeypatch, FakeProducer)
    from services.edge_ingest.connectors import mqtt as mqtt_mod

    async def run():
        queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        payload = {"source_protocol": "mqtt", "source_id": "ok", "value": 1}
        mqtt_mod.enqueue_mqtt_message(queue, payload, publisher, "ok")
        assert queue.qsize() == 1

    asyncio.run(run())

    assert all(p[0] != "industrial.dlq" for p in produced)
