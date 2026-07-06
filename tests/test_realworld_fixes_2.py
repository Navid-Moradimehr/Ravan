"""Regression tests for the second real-world correctness pass.

Covers:
- AI gateway no longer has duplicated broadcast/consume definitions.
- ingest endpoint publishes to Kafka and passes a dict to the historian.
- insert_processed_event stores the real tag/asset/value/unit and adapts lists/JSON.
- WebhookOutbound retries transient failures.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _source(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_ai_gateway_has_no_duplicate_definitions():
    """The broadcast loop and consume loop must each be defined exactly once."""
    tree = ast.parse(_source("services/ai_gateway/main.py"))
    names: dict[str, int] = {}
    # Only module-level (top-level) definitions matter for the duplication bug.
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names[node.name] = names.get(node.name, 0) + 1
    assert names.get("consume_loop", 0) == 1, "consume_loop duplicated"
    assert names.get("historian_broadcast_loop", 0) == 1, "historian_broadcast_loop duplicated"
    dupes = {k: v for k, v in names.items() if v > 1}
    assert not dupes, f"duplicate module-level definitions: {dupes}"


def test_ai_gateway_imports_settings_from_correct_module():
    src = _source("services/ai_gateway/main.py")
    assert "from services.ai_gateway.config import Settings" in src


def test_ingest_endpoint_publishes_kafka_and_passes_dict(monkeypatch):
    """Importing the api_service module should not require Kafka to be up.

    We patch confluent_kafka.Producer to capture publishes. Since the fan-out
    consumer now owns historian persistence, the API ingest must NOT call
    insert_industrial_event directly.
    """
    published: list[tuple[str, bytes, bytes]] = []

    class FakeProducer:
        def __init__(self, *args, **kwargs):
            pass

        def produce(self, topic, key=None, value=None, **kwargs):
            published.append((topic, key, value))

        def flush(self, timeout=None):
            return 0

    import sys
    import types

    fake = types.ModuleType("confluent_kafka")
    fake.Producer = FakeProducer
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake)

    captured: list[dict] = []

    def fake_insert(event):
        captured.append(event)

    # Reload client so our env tweaks stick, then patch insert_industrial_event.
    import importlib

    from services.historian import client as historian_client

    importlib.reload(historian_client)
    monkeypatch.setattr(historian_client, "insert_industrial_event", fake_insert)

    # Import api_service fresh.
    import services.api_service.main as api_main  # noqa: F401

    endpoint = api_main.ingest_event

    async def call_it():
        return await endpoint(
            {
                "source_protocol": "api",
                "source_id": "scada-1",
                "asset_id": "Pump-07",
                "tag": "DischargePressure",
                "value": 7.4,
                "unit": "bar",
            }
        )

    import asyncio

    result = asyncio.run(call_it())

    assert result["status"] == "ingested"
    # Published to raw + normalized + legacy.
    topics = {p[0] for p in published}
    assert "industrial.raw" in topics
    assert "industrial.normalized" in topics
    # The API no longer dual-writes to the historian; persistence is owned by
    # the normalized fan-out consumer.
    assert not captured, "API ingest must not write to the historian directly"


def test_ingest_endpoint_routes_invalid_to_dlq(monkeypatch):
    """Missing required fields -> DLQ topic, not a 500."""
    published: list[tuple[str, bytes, bytes]] = []

    class FakeProducer:
        def __init__(self, *a, **k):
            pass

        def produce(self, topic, key=None, value=None, **k2):
            published.append((topic, key, value))

        def flush(self, timeout=None):
            return 0

    import sys, types

    fake = types.ModuleType("confluent_kafka")
    fake.Producer = FakeProducer
    monkeypatch.setitem(sys.modules, "confluent_kafka", fake)

    import services.api_service.main as api_main
    from services.api_service import runtime as _runtime

    # The producer helper is lru_cached; clear it so this test's FakeProducer
    # is used instead of a producer cached by a prior test's monkeypatch.
    _runtime._get_producer.cache_clear()

    async def call_it():
        return await api_main.ingest_event({"source_protocol": "api", "value": 1})

    import asyncio

    result = asyncio.run(call_it())
    assert result["status"] == "rejected"
    assert any(p[0] == "industrial.dlq" for p in published)


def test_processed_events_schema_has_real_tag_columns():
    sql = _source("docker/postgres/init-timescale-full.sql")
    assert "asset_id TEXT NOT NULL" in sql
    assert "tag TEXT NOT NULL" in sql
    assert "value DOUBLE PRECISION" in sql
    assert "unit TEXT" in sql
    # Canonical schema declares tag natively (no legacy ALTER migration).
    assert "CREATE UNIQUE INDEX IF NOT EXISTS processed_events_event_id_uniq" in sql


def test_insert_processed_event_builds_correct_tuple(monkeypatch):
    """insert_processed_event must include the new columns and adapt lists/JSON."""
    captured: dict = {}

    class FakeCursor:
        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = list(params)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import importlib

    from services.historian import client as historian_client

    monkeypatch.setattr(historian_client, "get_connection", lambda: FakeConn())

    event = {
        "timestamp": "2026-01-01T00:00:00Z",
        "event_id": "e1",
        "device_id": "M-1",
        "asset_id": "M-1",
        "tag": "Torque",
        "value": 12.5,
        "unit": "Nm",
        "site_id": "site-1",
        "source_protocol": "opcua",
        "quality": "good",
        "schema_version": 1,
        "temperature_c": 0,
        "vibration_mm_s": 0,
        "pressure_bar": 0,
        "processed_at": "2026-01-01T00:00:01Z",
        "window_size": 3,
        "temperature_avg_c": 0,
        "vibration_avg_mm_s": 0,
        "anomaly_score": 0.42,
        "severity": "warning",
        "triggered_rules": ["r1", "r2"],
        "baseline": {"mean": 10},
        "evaluation": {"tp": 1},
    }
    historian_client.insert_processed_event(event)

    params = captured["params"]
    # New columns present in order: asset_id, tag, value, unit (positions 3-6).
    assert params[3] == "M-1"
    assert params[4] == "Torque"
    assert params[5] == 12.5
    assert params[6] == "Nm"
    # triggered_rules is a plain list (psycopg2 adapts), baseline/evaluation wrapped in Json.
    from psycopg2.extras import Json

    assert params[-3] == ["r1", "r2"]
    assert isinstance(params[-2], Json)
    assert isinstance(params[-1], Json)


def test_webhook_outbound_retries_on_5xx(monkeypatch):
    from services.api_service import notifications as notif_mod

    class FakeResponse:
        def __init__(self, statuses):
            self._statuses = statuses
            self._i = 0

        @property
        def status_code(self):
            s = self._statuses[min(self._i, len(self._statuses) - 1)]
            self._i += 1
            return s

    class FakeSession:
        def __init__(self, statuses):
            self._resp = FakeResponse(statuses)

        def post(self, url, json=None, headers=None):
            return self._resp

    wh = notif_mod.WebhookOutbound([{"url": "http://example/hook", "events": ["alarm"]}], max_retries=3)
    monkeypatch.setattr(wh, "_get_session", lambda: FakeSession([500, 500, 200]))
    monkeypatch.setattr(notif_mod.time, "sleep", lambda *_a, **_k: None) if hasattr(notif_mod, "time") else None
    # _time is imported inside send(); patch builtins via a module-level sleep isn't trivial,
    # so just allow the real tiny backoff — it's only 0.5s+1.5s. Keep test fast by patching time.
    import types

    real_time = __import__("time")
    monkeypatch.setattr(real_time, "sleep", lambda *_a, **_k: None)

    result = wh.send({"event_type": "alarm", "message": "x"})
    assert result["sent"] is True
    assert result["results"][0]["attempts"] == 3
    assert result["results"][0]["ok"] is True


def test_webhook_outbound_gives_up_after_max_retries(monkeypatch):
    from services.api_service import notifications as notif_mod

    class FakeResponse:
        status_code = 503

    class FakeSession:
        def post(self, url, json=None, headers=None):
            return FakeResponse()

    wh = notif_mod.WebhookOutbound([{"url": "http://example/hook", "events": ["alarm"]}], max_retries=1)
    monkeypatch.setattr(wh, "_get_session", lambda: FakeSession())
    real_time = __import__("time")
    monkeypatch.setattr(real_time, "sleep", lambda *_a, **_k: None)

    result = wh.send({"event_type": "alarm"})
    assert result["sent"] is False
    assert result["results"][0]["attempts"] == 2  # initial + 1 retry


def test_notifications_no_stray_add_channel_at_module_level():
    """The broken duplicate add_channel must be gone from module scope."""
    tree = ast.parse(_source("services/api_service/notifications.py"))
    module_level_funcs = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert "add_channel" not in module_level_funcs
    # And it must now live inside AppriseNotifier.
    appr = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AppriseNotifier"
    )
    methods = {n.name for n in appr.body if isinstance(n, ast.FunctionDef)}
    assert "add_channel" in methods


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
