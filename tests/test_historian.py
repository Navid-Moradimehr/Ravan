from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from services.historian.client import _connection_string


def test_connection_string_uses_env_vars() -> None:
    os.environ["TIMESCALE_HOST"] = "testhost"
    os.environ["TIMESCALE_PORT"] = "9999"
    os.environ["TIMESCALE_DB"] = "testdb"
    os.environ["TIMESCALE_USER"] = "testuser"
    os.environ["TIMESCALE_PASSWORD"] = "testpass"
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
