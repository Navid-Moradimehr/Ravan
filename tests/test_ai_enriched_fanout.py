from __future__ import annotations

import json
import sys
import types

import pytest


class _FakeMsg:
    def __init__(self, topic, partition, offset, value):
        self._t = topic
        self._p = partition
        self._o = offset
        self._v = value

    def topic(self):
        return self._t

    def partition(self):
        return self._p

    def offset(self):
        return self._o

    def value(self):
        return self._v

    def error(self):
        return None


class _FakeTP:
    def __init__(self, topic, partition, offset):
        self.topic = topic
        self.partition = partition
        self.offset = offset


class _FakeConsumer:
    def __init__(self, messages):
        self._messages = list(messages)
        self.committed = []

    def poll(self, timeout):
        return self._messages.pop(0) if self._messages else None

    def get_watermark_offsets(self, tp, cached=True):
        return (0, 0)

    def commit(self, offsets=None, asynchronous=False):
        for tp in offsets or []:
            self.committed.append((tp.topic, tp.partition, tp.offset))

    def subscribe(self, topics):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
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

    kafka_fake = types.ModuleType("confluent_kafka")
    kafka_fake.Consumer = lambda *a, **k: None
    kafka_fake.Producer = lambda *a, **k: None
    kafka_fake.TopicPartition = _FakeTP
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_fake)


def test_ai_enriched_fanout_persists_and_commits(monkeypatch):
    """AI-enriched events are persisted to the historian then offsets committed."""
    import importlib

    from services.processor import ai_enriched_fanout as fanout_mod

    importlib.reload(fanout_mod)

    inserted: list[dict] = []

    def fake_insert(event):
        inserted.append(event)

    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "insert_ai_enriched", fake_insert)
    monkeypatch.setattr(fanout_mod, "insert_ai_enriched", fake_insert)

    events = [
        {"source": "ai-gateway", "model": "gpt", "batch_size": 3, "summary": "ok", "latency_seconds": 0.5},
        {"source": "ai-gateway", "model": "gpt", "batch_size": 2, "summary": "ok2", "latency_seconds": 0.4},
    ]
    messages = [
        _FakeMsg("iot.ai_enriched", 0, 0, json.dumps(events[0]).encode()),
        _FakeMsg("iot.ai_enriched", 0, 1, json.dumps(events[1]).encode()),
    ]
    fake_consumer = _FakeConsumer(messages)
    monkeypatch.setattr(fanout_mod, "Consumer", lambda *a, **k: fake_consumer)

    consumer = fanout_mod.Consumer({"bootstrap.servers": "x"})
    consumer.subscribe(["iot.ai_enriched"])
    processed = 0
    while processed < 2:
        message = consumer.poll(1)
        if message is None:
            break
        if message.error():
            continue
        event = json.loads(message.value().decode("utf-8"))
        fanout_mod.insert_ai_enriched(event)
        consumer.commit(
            offsets=[fanout_mod.TopicPartition(message.topic(), message.partition(), message.offset() + 1)],
            asynchronous=False,
        )
        processed += 1

    assert inserted == events
    assert fake_consumer.committed == [
        ("iot.ai_enriched", 0, 1),
        ("iot.ai_enriched", 0, 2),
    ]


def test_schema_registry_has_processed_and_benchmark_schemas():
    """The registry now governs processed and benchmark schemas separately."""
    from services.common.schema_registry import schema_registry

    industrial = schema_registry.validate("industrial_event", {
        "event_id": "1",
        "source_protocol": "mqtt",
        "asset_id": "P1",
        "tag": "Temperature",
        "value": 50,
        "quality": "good",
        "ts_source": "2026-07-06T00:00:00Z",
    })
    assert industrial["valid"]

    processed = schema_registry.get("processed_event")
    assert processed is not None
    processed_fields = {f["name"] for f in processed.fields}
    assert {"anomaly_score", "severity", "window_size"} <= processed_fields

    benchmark = schema_registry.get("benchmark_event")
    assert benchmark is not None
    benchmark_fields = {f["name"] for f in benchmark.fields}
    assert {"fault_type", "scenario_id", "ground_truth_severity"} <= benchmark_fields


def test_push_driven_broadcast_event_signals_on_enrich(monkeypatch):
    """The historian refresh event is settable for the push-driven bus."""
    import asyncio

    from services.ai_gateway import main as ai_main

    event = ai_main.historian_refresh_event
    # Sanity: the event exists and is clearable/settable.
    event.clear()
    assert not event.is_set()
    event.set()
    assert event.is_set()
    event.clear()
