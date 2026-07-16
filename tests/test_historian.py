from __future__ import annotations

from unittest.mock import MagicMock, patch

import psycopg2
import pytest

from services.historian.client import _connection_string, _event_uuid, _industrial_dimensions, _typed_value


def test_connection_string_uses_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("TIMESCALE_HOST", "testhost")
    monkeypatch.setenv("TIMESCALE_PORT", "9999")
    monkeypatch.setenv("TIMESCALE_DB", "testdb")
    monkeypatch.setenv("TIMESCALE_USER", "testuser")
    monkeypatch.setenv("TIMESCALE_PASSWORD", "testpass")
    conn = _connection_string()
    assert "testhost:9999/testdb" in conn
    assert "testuser:testpass" in conn


def test_historian_boundary_preserves_scalar_types_and_external_ids() -> None:
    numeric = _typed_value(12.5)
    boolean = _typed_value(True)
    text = _typed_value("RUNNING")

    assert numeric == (12.5, None, None, "number")
    assert boolean == (1.0, None, True, "boolean")
    assert text == (0.0, "RUNNING", None, "string")
    assert _event_uuid("evt-808070") == _event_uuid("evt-808070")
    assert len(_event_uuid("evt-808070")) == 36


def test_sparse_industrial_dimensions_get_stable_defaults() -> None:
    assert _industrial_dimensions({"event_id": "evt-1"}) == (
        "unknown",
        "evt-1",
        "evt-1",
        "value",
    )


def test_insert_industrial_event_builds_correct_sql() -> None:
    # Mock the database connection and cursor
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda self: mock_cur
    mock_conn.cursor.return_value.__exit__ = lambda self, *args: None

    with patch("services.historian.client.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__ = lambda self: mock_conn
        mock_get_conn.return_value.__exit__ = lambda self, *args: None

        from services.historian.client import insert_industrial_event

        event = {
            "ts_ingest": "2026-06-27T10:00:00+00:00",
            "event_id": "evt-1",
            "source_protocol": "mqtt",
            "source_id": "factory/line-01/Pump-01/Temperature",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 51.2,
            "quality": "good",
            "unit": "c",
            "site": "demo-site",
            "line": "line-01",
            "schema_version": 1,
            "fault_type": "normal",
            "scenario_id": "sc-001",
            "ground_truth_severity": "normal",
            "step": 0,
        }
        insert_industrial_event(event)
        mock_cur.execute.assert_called_once()
        call_args = mock_cur.execute.call_args[0]
        assert "INSERT INTO industrial_events" in call_args[0]


def test_insert_industrial_events_uses_execute_values(monkeypatch) -> None:
    from services.historian import client

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            captured["committed"] = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_execute_values(cur, query, rows, page_size=None):
        captured["query"] = query
        captured["rows"] = list(rows)

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client, "execute_values", fake_execute_values)

    client.insert_industrial_events(
        [
            {
                "ts_ingest": "2026-06-27T10:00:00+00:00",
                "event_id": "evt-1",
                "source_protocol": "mqtt",
                "source_id": "factory/line-01/Pump-01/Temperature",
                "asset_id": "Pump-01",
                "tag": "Temperature",
                "value": 51.2,
                "quality": "good",
                "unit": "c",
                "site": "demo-site",
                "line": "line-01",
                "schema_version": 1,
                "fault_type": "normal",
                "scenario_id": "sc-001",
                "ground_truth_severity": "normal",
                "step": 0,
            },
            {
                "ts_ingest": "2026-06-27T10:00:01+00:00",
                "event_id": "evt-2",
                "source_protocol": "mqtt",
                "source_id": "factory/line-01/Pump-01/Vibration",
                "asset_id": "Pump-01",
                "tag": "Vibration",
                "value": 6.8,
                "quality": "good",
                "unit": "mm/s",
                "site": "demo-site",
                "line": "line-01",
                "schema_version": 1,
                "fault_type": "normal",
                "scenario_id": "sc-001",
                "ground_truth_severity": "normal",
                "step": 1,
            },
        ]
    )

    assert "industrial_events" in captured["query"]
    assert len(captured["rows"]) == 2
    assert captured["committed"] is True


def test_insert_industrial_events_preserves_canonical_site_id(monkeypatch) -> None:
    from services.historian import client

    captured: dict[str, object] = {}

    class FakeCursor:
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
    monkeypatch.setattr(client, "execute_values", lambda cur, query, rows, page_size=None: captured.update(rows=list(rows)))

    client.insert_industrial_events(
        [{
            "event_id": "site-event-1",
            "site_id": "plant-a",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 42,
        }]
    )

    assert captured["rows"][0][12] == "plant-a"


def test_insert_industrial_events_prefers_source_timestamp(monkeypatch) -> None:
    from services.historian import client

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class FakeConn:
        def cursor(self): return FakeCursor()
        def commit(self): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client, "execute_values", lambda cur, query, rows, page_size=None: captured.update(rows=list(rows)))

    client.insert_industrial_events([{
        "event_id": "timestamp-1",
        "source_protocol": "opcua",
        "source_id": "plc-1",
        "asset_id": "pump-1",
        "tag": "Temperature",
        "value": 42.0,
        "ts_source": "2026-01-01T00:00:00Z",
        "ts_ingest": "2026-01-01T00:00:09Z",
    }])

    assert captured["rows"][0][0] == "2026-01-01T00:00:00Z"


def test_insert_processed_events_preserves_string_scalar_columns(monkeypatch) -> None:
    from services.historian import client

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class FakeConn:
        def cursor(self): return FakeCursor()
        def commit(self): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client, "execute_values", lambda cur, query, rows, page_size=None: captured.update(query=query, rows=list(rows)))

    client.insert_processed_events([{
        "event_id": "state-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "asset_id": "pump-1",
        "tag": "State",
        "value": 0.0,
        "value_text_raw": "RUNNING",
        "value_bool": None,
        "value_type": "string",
    }])

    row = captured["rows"][0]
    assert row[5:9] == (0.0, "RUNNING", None, "string")
    assert "value_text_raw, value_bool, value_type" in captured["query"]


def test_insert_processed_events_uses_execute_values(monkeypatch) -> None:
    from services.historian import client

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            captured["committed"] = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_execute_values(cur, query, rows, page_size=None):
        captured["query"] = query
        captured["rows"] = list(rows)

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client, "execute_values", fake_execute_values)

    client.insert_processed_events(
        [
            {
                "timestamp": "2026-06-27T10:01:00+00:00",
                "event_id": "evt-3",
                "device_id": "Pump-01",
                "asset_id": "Pump-01",
                "tag": "Temperature",
                "value": 66.4,
                "unit": "c",
                "site_id": "demo-site",
                "source_protocol": "mqtt",
                "quality": "good",
                "schema_version": 1,
                "temperature_c": 66.4,
                "vibration_mm_s": 0.0,
                "pressure_bar": 0.0,
                "processed_at": "2026-06-27T10:01:01+00:00",
                "window_size": 8,
                "temperature_avg_c": 61.2,
                "vibration_avg_mm_s": 3.4,
                "anomaly_score": 0.7,
                "severity": "warning",
                "triggered_rules": ["high_temp"],
                "baseline": {"anomaly_score": 44},
                "evaluation": {"correct": True},
            }
        ]
    )

    assert "processed_events" in captured["query"]
    assert len(captured["rows"]) == 1
    assert captured["committed"] is True


def test_insert_processed_events_uses_on_conflict(monkeypatch) -> None:
    from services.historian import client

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            captured["committed"] = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_execute_values(cur, query, rows, page_size=None):
        captured["query"] = query
        captured["rows"] = list(rows)

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client, "execute_values", fake_execute_values)

    client.insert_processed_events(
        [
            {
                "timestamp": "2026-06-27T10:01:00+00:00",
                "event_id": "evt-dedup",
                "device_id": "Pump-01",
                "asset_id": "Pump-01",
                "tag": "Temperature",
                "value": 66.4,
                "unit": "c",
                "site_id": "demo-site",
                "source_protocol": "mqtt",
                "quality": "good",
                "schema_version": 1,
                "temperature_c": 66.4,
                "vibration_mm_s": 0.0,
                "pressure_bar": 0.0,
                "processed_at": "2026-06-27T10:01:01+00:00",
                "window_size": 8,
                "temperature_avg_c": 61.2,
                "vibration_avg_mm_s": 3.4,
                "anomaly_score": 0.7,
                "severity": "warning",
                "triggered_rules": ["high_temp"],
                "baseline": {"anomaly_score": 44},
                "evaluation": {"correct": True},
            }
        ]
    )

    assert "ON CONFLICT (time, event_id) DO NOTHING" in captured["query"]
    assert captured["committed"] is True


def test_composite_dimensions_use_device_identity() -> None:
    from services.historian.client import _industrial_dimensions, _typed_event_value, _typed_industrial_value

    event = {
        "device_id": "compressor-07",
        "temperature_c": 73.4,
        "vibration_mm_s": 4.8,
        "pressure_bar": 8.2,
    }
    assert _industrial_dimensions(event) == ("unknown", "compressor-07", "compressor-07", "__composite__")
    assert _typed_industrial_value(event) == (0.0, None, None, "composite")
    assert _typed_event_value({"value": 0.0, "value_type": "composite"}) == (
        0.0,
        None,
        None,
        "composite",
    )


def test_query_alarms_includes_triggering_value_and_unit(monkeypatch) -> None:
    from services.historian import client

    monkeypatch.setattr(
        client,
        "_fetch_rows",
        lambda *args, **kwargs: [{
            "time": "2026-06-27T10:01:00+00:00",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 96.5,
            "unit": "degC",
            "severity": "critical",
            "triggered_rules": ["temp_high"],
        }],
    )

    alarms = client.query_alarms(5)

    assert alarms[0]["value"] == 96.5
    assert alarms[0]["unit"] == "degC"


def test_query_sql_readonly_applies_timeout_and_tracks_handle(monkeypatch) -> None:
    from services.historian import client

    client._ACTIVE_QUERIES.clear()
    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, query, params=None):
            captured.setdefault("queries", []).append((query, params))

        def fetchall(self):
            return [{"event_id": "evt-1", "value": 42}]

    class FakeConn:
        def cursor(self, *args, **kwargs):
            captured["cursor_kwargs"] = kwargs
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    observed: list[tuple[object, ...]] = []
    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client, "observe_historian_query", lambda *args: observed.append(args))

    rows = client.query_sql_readonly(
        "SELECT * FROM industrial_events LIMIT 1",
        query_id="query-1",
        timeout_ms=1234,
    )

    assert rows == [{"event_id": "evt-1", "value": 42}]
    assert observed and observed[0][0] == "sql"
    assert observed[0][1] == "readonly"
    assert client._ACTIVE_QUERIES == {}
    assert any("set_config('statement_timeout'" in query for query, _ in captured["queries"])  # type: ignore[index]


def test_cancel_historian_query_calls_connection_cancel() -> None:
    from services.historian import client

    client._ACTIVE_QUERIES.clear()

    class FakeConn:
        def __init__(self):
            self.cancel_called = False

        def cancel(self):
            self.cancel_called = True

    conn = FakeConn()
    client._ACTIVE_QUERIES["query-2"] = client.HistorianQueryHandle(
        query_id="query-2",
        connection=conn,
        started_at=0.0,
        timeout_ms=1500,
        operation="readonly",
        sql="SELECT 1",
    )

    result = client.cancel_historian_query("query-2")

    assert result["status"] == "cancel_requested"
    assert conn.cancel_called is True
    client._ACTIVE_QUERIES.clear()


def test_query_sql_readonly_raises_timeout_when_statement_cancels(monkeypatch) -> None:
    from services.historian import client

    client._ACTIVE_QUERIES.clear()

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, query, params=None):
            if "industrial_events" in query:
                raise psycopg2.errors.QueryCanceled("canceling statement due to statement timeout")

        def fetchall(self):
            return []

    class FakeConn:
        def cursor(self, *args, **kwargs):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(client, "get_connection", lambda: FakeConn())

    with pytest.raises(client.HistorianQueryTimeoutError):
        client.query_sql_readonly(
            "SELECT * FROM industrial_events LIMIT 1",
            query_id="query-3",
            timeout_ms=1,
        )
