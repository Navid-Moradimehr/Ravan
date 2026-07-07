from __future__ import annotations

import sys
import types

import pytest

from services.sinks.base import CompositeSink, SinkRegistry


@pytest.fixture(autouse=True)
def _stub_psycopg2(monkeypatch):
    """Stub psycopg2 so the historian client imports without the native DLL.

    The Windows venv psycopg2 wheel's native _psycopg module fails to load in
    some environments; stubbing it lets historian-dependent unit tests import
    cleanly without touching a real database.
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



class RecordingSink:
    """Minimal Sink implementation that records written batches."""

    name = "recording"

    def __init__(self, fail: bool = False) -> None:
        self.written: list[dict] = []
        self.flushed = False
        self.closed = False
        self.fail = fail

    def write_batch(self, events):
        if self.fail:
            raise RuntimeError("boom")
        self.written.extend(events)
        return len(events)

    def flush(self):
        self.flushed = True

    def close(self):
        self.closed = True


def test_composite_sink_fans_out_to_all_sinks():
    a = RecordingSink()
    b = RecordingSink()
    composite = CompositeSink([a, b])

    events = [{"event_id": "1"}, {"event_id": "2"}]
    accepted = composite.write_batch(events)

    assert accepted == 4  # 2 events * 2 sinks
    assert a.written == events
    assert b.written == events


def test_composite_sink_empty_batch_is_noop():
    sink = RecordingSink()
    composite = CompositeSink([sink])
    assert composite.write_batch([]) == 0
    assert sink.written == []


def test_composite_sink_isolates_sink_failure():
    failing = RecordingSink(fail=True)
    healthy = RecordingSink()
    composite = CompositeSink([failing, healthy])

    events = [{"event_id": "1"}]
    # Should not raise; the healthy sink still receives the batch.
    accepted = composite.write_batch(events)

    assert healthy.written == events
    assert accepted == 1  # only the healthy sink accepted


def test_composite_sink_strict_write_raises_on_sink_failure():
    failing = RecordingSink(fail=True)
    healthy = RecordingSink()
    composite = CompositeSink([failing, healthy])

    with pytest.raises(RuntimeError):
        composite.write_batch_strict([{"event_id": "1"}])

    assert healthy.written == [{"event_id": "1"}]


def test_composite_sink_strict_write_raises_on_partial_acceptance():
    class PartialSink(RecordingSink):
        name = "partial"

        def write_batch(self, events):
            self.written.extend(events[:1])
            return 1

    composite = CompositeSink([PartialSink()])

    with pytest.raises(RuntimeError, match="accepted 1/2"):
        composite.write_batch_strict([{"event_id": "1"}, {"event_id": "2"}])


def test_composite_sink_strict_flush_raises_on_failure():
    class FlushFailSink(RecordingSink):
        name = "flush-fail"

        def flush(self):
            raise RuntimeError("flush failed")

    composite = CompositeSink([FlushFailSink()])

    with pytest.raises(RuntimeError, match="flush failed"):
        composite.flush_strict()


def test_composite_sink_strict_flush_uses_sink_strict_hook():
    class StrictOnlySink(RecordingSink):
        name = "strict-only"

        def flush(self):
            self.flushed = True

        def flush_strict(self):
            raise RuntimeError("strict failure")

    composite = CompositeSink([StrictOnlySink()])

    with pytest.raises(RuntimeError, match="strict failure"):
        composite.flush_strict()


def test_composite_sink_flush_and_close_propagate():
    a = RecordingSink()
    b = RecordingSink()
    composite = CompositeSink([a, b])

    composite.flush()
    composite.close()

    assert a.flushed and b.flushed
    assert a.closed and b.closed


def test_composite_sink_context_manager_closes():
    a = RecordingSink()
    with CompositeSink([a]) as composite:
        composite.write_batch([{"event_id": "1"}])
    assert a.closed


def test_registry_returns_empty_composite_when_sinks_unset(monkeypatch):
    monkeypatch.delenv("SINKS", raising=False)
    composite = SinkRegistry.from_env()
    assert composite.sinks == []


def test_registry_skips_unknown_sink_name(monkeypatch):
    monkeypatch.setenv("SINKS", "definitely-not-a-sink")
    composite = SinkRegistry.from_env()
    assert composite.sinks == []


def test_registry_builds_historian_sink(monkeypatch):
    """The historian sink is buildable from env when psycopg2 is importable."""
    monkeypatch.setenv("SINKS", "historian")
    composite = SinkRegistry.from_env()
    assert len(composite.sinks) == 1
    assert composite.sinks[0].name == "historian"


def test_historian_sink_uses_batch_insert(monkeypatch):
    """TimescaleHistorianSink delegates to the historian client batch insert."""
    captured: list[list[dict]] = []

    def fake_batch(events):
        captured.append(list(events))

    monkeypatch.setenv("SINKS", "historian")
    # Patch the insert function on the historian client module that the sink imports.
    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "insert_industrial_events", fake_batch)
    from services.sinks.historian_sink import TimescaleHistorianSink

    sink = TimescaleHistorianSink()
    events = [{"event_id": "1"}, {"event_id": "2"}]
    accepted = sink.write_batch(events)

    assert accepted == 2
    assert captured == [events]


def test_historian_sink_falls_back_per_event(monkeypatch):
    """A batch-insert failure triggers per-event fallback insertion."""
    single_calls: list[dict] = []

    def failing_batch(events):
        raise RuntimeError("batch failed")

    def fake_single(event):
        single_calls.append(event)

    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "insert_industrial_events", failing_batch)
    monkeypatch.setattr(historian_client, "insert_industrial_event", fake_single)
    from services.sinks.historian_sink import TimescaleHistorianSink

    sink = TimescaleHistorianSink()
    events = [{"event_id": "1"}, {"event_id": "2"}]
    accepted = sink.write_batch(events)

    assert accepted == 2
    assert single_calls == events


def test_kafka_sink_builds_and_writes(monkeypatch):
    """KafkaSink forwards events to a downstream topic using the composite key."""
    produced: list[tuple[str, bytes, bytes]] = []
    flush_calls = {"n": 0}

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, **kwargs):
            produced.append((topic, key, value))

        def poll(self, timeout=None):
            return 0

        def flush(self, timeout=None):
            flush_calls["n"] += 1
            return 0

    fake = types.ModuleType("confluent_kafka")
    fake.Producer = FakeProducer
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake)
    # Reload the kafka_sink module so it picks up the fake Producer.
    import importlib

    from services.sinks import kafka_sink as kafka_sink_mod

    importlib.reload(kafka_sink_mod)

    sink = kafka_sink_mod.KafkaSink(brokers="localhost:19092", topic="industrial.fanout", batch_size=2)
    events = [
        {
            "event_id": "1",
            "source_protocol": "mqtt",
            "source_id": "s1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "site": "demo-site",
            "line": "line-01",
            "value": 50,
            "quality": "good",
            "ts_source": "2026-07-06T00:00:00Z",
        },
        {
            "event_id": "2",
            "source_protocol": "mqtt",
            "source_id": "s2",
            "asset_id": "Pump-02",
            "tag": "Vibration",
            "site": "demo-site",
            "line": "line-01",
            "value": 5,
            "quality": "good",
            "ts_source": "2026-07-06T00:00:01Z",
        },
    ]
    accepted = sink.write_batch(events)
    sink.flush()
    sink.close()

    assert accepted == 2
    assert len(produced) == 2
    assert all(topic == "industrial.fanout" for topic, _, _ in produced)
    # Composite key includes the asset, so the two distinct assets differ.
    assert produced[0][1] != produced[1][1]
    assert flush_calls["n"] >= 2


def test_kafka_sink_flush_raises_when_messages_remain(monkeypatch):
    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, *a, **k):
            pass

        def flush(self, timeout=None):
            return 1

    fake = types.ModuleType("confluent_kafka")
    fake.Producer = FakeProducer
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake)

    import importlib

    from services.sinks import kafka_sink as kafka_sink_mod

    importlib.reload(kafka_sink_mod)

    sink = kafka_sink_mod.KafkaSink(brokers="localhost:19092", topic="industrial.fanout", batch_size=10)

    with pytest.raises(RuntimeError, match="delivery incomplete"):
        sink.flush()
