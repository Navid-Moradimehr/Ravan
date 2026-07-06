from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    kafka_fake = types.ModuleType("confluent_kafka")

    class _P:
        def __init__(self, *a, **k):
            pass

        def produce(self, *a, **k):
            pass

        def flush(self, t=None):
            return 0

        def poll(self, t=None):
            return 0

    kafka_fake.Producer = _P
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


def test_gateway_historian_rest_surface_removed():
    """The duplicate /historian/* REST reads must be gone (owned by the API)."""
    import re

    from pathlib import Path

    src = Path("services/ai_gateway/main.py").read_text(encoding="utf-8")
    removed = ["/historian/events", "/historian/trend", "/historian/assets",
               "/historian/scenarios", "/historian/alarms", "/historian/replay"]
    for path in removed:
        assert path not in src, f"gateway still exposes duplicate endpoint {path}"


def test_gateway_keeps_sse_stream():
    """The push-based /historian/stream SSE endpoint must remain."""
    from pathlib import Path

    src = Path("services/ai_gateway/main.py").read_text(encoding="utf-8")
    assert "/historian/stream" in src
    assert "/events" in src  # telemetry SSE


def test_gateway_keeps_ai_specific_endpoints():
    """AI-specific endpoints (telemetry, health, metrics) must remain."""
    from pathlib import Path

    src = Path("services/ai_gateway/main.py").read_text(encoding="utf-8")
    assert "@app.get(\"/telemetry\")" in src
    assert "@app.get(\"/health\")" in src
    assert "@app.get(\"/metrics\")" in src
