from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.historian.client import _connection_string


def test_connection_string_uses_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("TIMESCALE_HOST", "testhost")
    monkeypatch.setenv("TIMESCALE_PORT", "9999")
    monkeypatch.setenv("TIMESCALE_DB", "testdb")
    monkeypatch.setenv("TIMESCALE_USER", "testuser")
    monkeypatch.setenv("TIMESCALE_PASSWORD", "testpass")
    conn = _connection_string()
    assert "testhost:9999/testdb" in conn
    assert "testuser:testpass" in conn


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
