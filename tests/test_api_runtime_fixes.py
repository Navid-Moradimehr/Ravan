from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_kafka(monkeypatch):
    """Stub confluent_kafka + psycopg2 so the AI gateway / API import cleanly."""
    kafka_fake = types.ModuleType("confluent_kafka")

    class _FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, *a, **k):
            pass

        def flush(self, timeout=None):
            return 0

        def poll(self, timeout=None):
            return 0

    kafka_fake.Producer = _FakeProducer
    kafka_fake.Consumer = lambda *a, **k: None
    kafka_fake.TopicPartition = type("TP", (), {})
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_fake)

    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("Op", (Exception,), {})
    psycopg_fake.InterfaceError = type("Iface", (Exception,), {})
    psycopg_fake.Error = type("Err", (Exception,), {})
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda o: o
    extras_fake.RealDictCursor = type("RDC", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type("TCP", (), {"__init__": lambda *a, **k: None})
    psycopg_fake.extras = extras_fake
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)


def test_ai_gateway_sse_uses_running_attribute():
    """The SSE loops must use service_state.running, not item access."""
    import re

    from pathlib import Path

    src = Path("services/ai_gateway/main.py").read_text(encoding="utf-8")
    assert 'service_state["running"]' not in src, "SSE loop still uses item access"
    assert "service_state.running" in src


def test_runtime_ingest_does_not_write_historian(monkeypatch):
    """_do_ingest_event must not call insert_industrial_event (fan-out owns it)."""
    import inspect

    from services.api_service import runtime

    src = inspect.getsource(runtime._do_ingest_event)
    assert "insert_industrial_event" not in src, (
        "API ingest still writes to the historian directly"
    )


def test_runtime_has_single_publish_helper():
    """_publish_kafka_fresh must be removed (consolidated into _publish_kafka)."""
    from services.api_service import runtime

    assert hasattr(runtime, "_publish_kafka")
    assert not hasattr(runtime, "_publish_kafka_fresh"), (
        "_publish_kafka_fresh duplicate still present"
    )


def test_runtime_returns_published_event_id_and_publish_failed_status(monkeypatch):
    from services.api_service import runtime

    monkeypatch.setattr(runtime, "resolve_kafka_brokers", lambda default="x": "localhost:19092")
    monkeypatch.setattr(runtime, "_publish_kafka", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))

    result = runtime._do_ingest_event(
        {
            "source_protocol": "api",
            "source_id": "unit-test",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 42.0,
            "quality": "good",
            "unit": "C",
            "site": "demo-site",
            "line": "line-01",
        }
    )

    assert result["status"] == "publish_failed"
    assert result["event_id"]
    assert "kafka_publish_failed" in result["warning"]
