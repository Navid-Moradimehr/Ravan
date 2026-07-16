from __future__ import annotations

import json
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    """Stub psycopg2 so the historian client imports without the native DLL."""
    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("OperationalError", (Exception,), {})
    psycopg_fake.InterfaceError = type("InterfaceError", (Exception,), {})
    psycopg_fake.Error = type("Error", (Exception,), {})
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda obj: obj
    extras_fake.RealDictCursor = type("RealDictCursor", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type("ThreadedConnectionPool", (), {"__init__": lambda *a, **k: None})
    psycopg_fake.extras = extras_fake
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)


def test_partition_key_is_composite(monkeypatch):
    """The Flink partition key uses the 7-field composite scope, not asset-only."""
    from services.processor import iot_anomaly_job as flink_mod

    payload_a = {
        "asset_id": "Pump-01",
        "tag": "Temperature",
        "site": "demo-site",
        "line": "line-01",
        "source_protocol": "mqtt",
        "source_id": "s1",
    }
    payload_b = {
        "asset_id": "Pump-01",  # same asset...
        "tag": "Vibration",  # ...different tag
        "site": "demo-site",
        "line": "line-01",
        "source_protocol": "mqtt",
        "source_id": "s1",
    }
    raw_a = json.dumps(payload_a)
    raw_b = json.dumps(payload_b)

    key_a = flink_mod._partition_key(raw_a)
    key_b = flink_mod._partition_key(raw_b)

    # Same asset but different tag => different composite key (asset-only would collide).
    assert key_a != key_b
    assert "Pump-01" in key_a
    assert "Temperature" in key_a


def test_partition_key_handles_malformed_input():
    from services.processor import iot_anomaly_job as flink_mod

    assert flink_mod._partition_key("not-json") == "unknown"


def test_processed_events_sink_batches_and_flushes(monkeypatch):
    """ProcessedEventsSink accumulates payloads and flushes to the historian."""
    from services.processor import iot_anomaly_job as flink_mod

    batch_calls: list[list[dict]] = []
    single_calls: list[dict] = []

    def fake_batch(events):
        batch_calls.append(list(events))

    def fake_single(event):
        single_calls.append(event)

    # Patch the historian client functions that ProcessedEventsSink imports lazily.
    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "insert_processed_events", fake_batch)
    monkeypatch.setattr(historian_client, "insert_processed_event", fake_single)

    sink = flink_mod.ProcessedEventsSink(batch_size=3)
    payloads = [{"event_id": f"e{i}", "value": i} for i in range(5)]
    for p in payloads:
        sink.invoke(json.dumps(p))

    # After 3 invokes the buffer hits batch_size and flushes.
    assert len(batch_calls) == 1
    assert batch_calls[0] == payloads[:3]

    # Remaining 2 are buffered until explicit flush.
    sink.flush()
    assert len(batch_calls) == 2
    assert batch_calls[1] == payloads[3:]


def test_processed_events_sink_rejects_malformed(monkeypatch):
    """Malformed payloads fail visibly instead of being checkpointed as processed."""
    from services.processor import iot_anomaly_job as flink_mod

    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "insert_processed_events", lambda e: None)
    monkeypatch.setattr(historian_client, "insert_processed_event", lambda e: None)

    sink = flink_mod.ProcessedEventsSink(batch_size=10)
    with pytest.raises(ValueError, match="invalid processed event"):
        sink.invoke("not-json{")


def test_processed_events_sink_falls_back_per_event(monkeypatch):
    """A batch-insert failure triggers per-event fallback."""
    from services.processor import iot_anomaly_job as flink_mod

    single_calls: list[dict] = []

    def failing_batch(events):
        raise RuntimeError("batch failed")

    def fake_single(event):
        single_calls.append(event)

    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "insert_processed_events", failing_batch)
    monkeypatch.setattr(historian_client, "insert_processed_event", fake_single)

    sink = flink_mod.ProcessedEventsSink(batch_size=2)
    events = [{"event_id": "1"}, {"event_id": "2"}]
    for e in events:
        sink.invoke(json.dumps(e))
    sink.flush()

    assert single_calls == events


def test_processed_events_sink_does_not_swallow_persistent_write_failure(monkeypatch):
    from services.processor import iot_anomaly_job as flink_mod
    from services.historian import client as historian_client

    monkeypatch.setattr(
        historian_client,
        "insert_processed_events",
        lambda events: (_ for _ in ()).throw(RuntimeError("batch failed")),
    )
    monkeypatch.setattr(
        historian_client,
        "insert_processed_event",
        lambda event: (_ for _ in ()).throw(RuntimeError("single failed")),
    )

    sink = flink_mod.ProcessedEventsSink(batch_size=2)
    sink.invoke(json.dumps({"event_id": "1"}))
    with pytest.raises(RuntimeError, match="historian rejected 2 of 2"):
        sink.invoke(json.dumps({"event_id": "2"}))
    assert len(sink._buffer) == 2
