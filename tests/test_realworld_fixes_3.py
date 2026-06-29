"""Regression tests for real-world correctness pass 3.

Covers:
- Compression segmentby uses only columns that exist per table (ai_enriched bug).
- insert_* helpers run writes through _execute_with_retry (transient retry).
- Dead-letter events persist via insert_dead_letter.
- DLQ table + endpoint exist in schema/api.
- Silent excepts in the data path now log (structural guard).
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _source(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_compression_segmentby_matches_table_columns():
    """ai_enriched has no asset_id/tag; segmentby must differ per table."""
    src = _source("services/historian/client.py")
    tree = ast.parse(src)
    setup = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "setup_retention_policies"
    )
    # Find the compress_segmentby dict literal.
    segmentby_node = None
    for node in ast.walk(setup):
        if isinstance(node, ast.Dict):
            keys = [k.value if isinstance(k, ast.Constant) else None for k in node.keys]
            if "industrial_events" in keys and "ai_enriched" in keys:
                segmentby_node = node
                break
    assert segmentby_node is not None, "compress_segmentby per-table mapping missing"
    vals = {k.value: v.value for k, v in zip(segmentby_node.keys, segmentby_node.values)}
    assert "asset_id, tag" in vals["industrial_events"]
    assert "asset_id, tag" in vals["processed_events"]
    # ai_enriched must NOT reference asset_id/tag (those columns don't exist there).
    assert "asset_id" not in vals["ai_enriched"]
    assert "tag" not in vals["ai_enriched"]


def test_schema_has_dead_letter_table_and_processed_columns():
    sql = _source("postgres/init-timescale.sql")
    assert "CREATE TABLE IF NOT EXISTS dead_letter_events" in sql
    assert "payload JSONB" in sql
    assert "origin TEXT" in sql
    assert "create_hypertable('dead_letter_events'" in sql
    # processed_events still has the pass-2 columns.
    assert "ADD COLUMN IF NOT EXISTS tag TEXT" in sql


def test_insert_helpers_use_retry():
    """All three insert_* functions must delegate to _execute_with_retry."""
    from services.historian import client

    for name in ("insert_industrial_event", "insert_processed_event", "insert_ai_enriched", "insert_dead_letter"):
        fn = getattr(client, name)
        src = inspect.getsource(fn)
        assert "_execute_with_retry" in src, f"{name} must use _execute_with_retry"


def test_execute_with_retry_retries_then_succeeds(monkeypatch):
    from services.historian import client

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise client.psycopg2.OperationalError("server closed the connection")
        # success on 3rd

    # No real sleep during retry.
    monkeypatch.setattr(client.time, "sleep", lambda *_a, **_k: None)
    # Make pool recycle a no-op.
    class _FakePool:
        def closeall(self):
            pass
        def cache_clear(self):
            pass
    monkeypatch.setattr(client, "_connection_pool", lambda: _FakePool())

    client._execute_with_retry("processed_events", flaky)
    assert calls["n"] == 3


def test_execute_with_retry_raises_after_max(monkeypatch):
    from services.historian import client

    def always_fail():
        raise client.psycopg2.OperationalError("unreachable db")

    monkeypatch.setattr(client.time, "sleep", lambda *_a, **_k: None)

    class _FakePool:
        def closeall(self):
            pass
        def cache_clear(self):
            pass
    monkeypatch.setattr(client, "_connection_pool", lambda: _FakePool())

    # Force zero retries via env-reload: monkeypatch the module constants.
    monkeypatch.setattr(client, "WRITE_MAX_RETRIES", 1)

    with pytest.raises(client.psycopg2.OperationalError):
        client._execute_with_retry("processed_events", always_fail)


def test_insert_dead_letter_builds_correct_tuple(monkeypatch):
    from services.historian import client

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

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    client.insert_dead_letter(
        {
            "event_id": "e1",
            "source_protocol": "api",
            "source_id": "scada-1",
            "error": "value must not be empty",
            "payload": {"tag": ""},
            "origin": "api",
        }
    )
    params = captured["params"]
    assert "dead_letter_events" in captured["query"]
    # payload wrapped as Json.
    from psycopg2.extras import Json

    assert any(isinstance(p, Json) for p in params)
    assert params[3] == "scada-1"  # source_id
    assert "value must not be empty" in params  # error text


def test_data_path_swallows_are_logged():
    """The bare `except Exception: pass` in processor/edge/ai_gateway broadcast
    must be replaced with logged exceptions (structural guard on source)."""
    processor = _source("services/processor/runtime_processor.py")
    edge = _source("services/edge_ingest/main.py")
    ai = _source("services/ai_gateway/main.py")
    # The specific silent swallow around insert_processed_event is gone.
    assert "insert_processed_event(event)\n            except Exception:\n                pass" not in processor
    assert "insert_industrial_event(event.model_dump(mode=\"json\"))\n            except Exception:\n                pass" not in edge
    # broadcast loop logs rather than bare-pass.
    assert "historian broadcast loop error" in ai


def test_dlq_endpoint_registered():
    """The dead-letters query endpoint must exist on the app."""
    import services.api_service.main as api_main

    routes = {r.path for r in api_main.app.routes}
    assert "/api/v1/historian/dead-letters" in routes


def test_auto_setup_retention_in_lifespan():
    src = _source("services/api_service/main.py")
    assert "setup_retention_policies()" in src
    assert "HISTORIAN_AUTO_SETUP" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
