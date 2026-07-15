from __future__ import annotations

from pathlib import Path

import pytest

from services.historian import backup as hb


def test_restore_toc_excludes_timescaledb_owned_public_schema():
    toc = "1; 2615 2200 SCHEMA - public\n2; 0 0 COMMENT - SCHEMA public\n3; 10 20 TABLE - industrial_events\n"
    filtered = hb._without_public_schema_entries(toc)
    assert "SCHEMA - public" not in filtered
    assert "industrial_events" in filtered


def test_create_backup_uses_docker_fallback_when_pg_dump_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(hb.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(
        hb,
        "_create_backup_via_docker",
        lambda filepath, conn, tables: {"status": "success", "path": str(filepath), "transport": "docker:timescaledb"},
    )
    result = hb.create_backup(backup_dir=str(tmp_path))
    assert result["status"] == "success"
    assert result["transport"] == "docker:timescaledb"


def test_restore_backup_uses_docker_fallback_when_pg_restore_missing(monkeypatch, tmp_path):
    backup_path = tmp_path / "historian_backup_20260630_120000.sql"
    backup_path.write_bytes(b"test")
    monkeypatch.setattr(hb.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(
        hb,
        "_restore_backup_via_docker",
        lambda filepath, conn: {"status": "success", "backup_path": str(filepath), "transport": "docker:timescaledb"},
    )
    result = hb.restore_backup(str(backup_path), "restore_db")
    assert result["status"] == "success"
    assert result["transport"] == "docker:timescaledb"


def test_snapshot_uses_docker_fallback_when_psql_missing(monkeypatch):
    from services.historian import backup

    monkeypatch.setattr(backup, "_detect_docker_db_service", lambda: "timescaledb")
    monkeypatch.setattr(
        backup.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"stdout": "industrial_events|3\nprocessed_events|2\n", "stderr": "", "returncode": 0})(),
    )
    monkeypatch.setattr(backup, "_connection_params", lambda: {"host": "localhost", "port": "5432", "database": "stream_engine", "user": "stream", "password": "stream"})
    result = backup._collect_historian_snapshot_via_docker(("industrial_events", "processed_events"), backup._connection_params())
    assert result["status"] == "success"
    assert result["transport"] == "docker:timescaledb"
    assert result["row_count_total"] == 5


def test_snapshot_can_target_restored_database(monkeypatch):
    from services.historian import backup

    captured = {}
    monkeypatch.setattr(backup, "_connection_params", lambda: {"host": "localhost", "port": "5432", "database": "stream_engine", "user": "stream", "password": "stream"})
    def fake_run(command, **kwargs):
        captured["command"] = command
        return type("Result", (), {"stdout": "industrial_events|4\n", "stderr": "", "returncode": 0})()

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    result = backup.collect_historian_snapshot(("industrial_events",), database="restore_db")
    assert result["database"] == "restore_db"
    assert "restore_db" in captured["command"]


def test_timescale_restore_sql_includes_expected_hypertables():
    sql = hb._timescale_restore_sql()
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE" in sql
    assert "SELECT timescaledb_post_restore()" in sql
    assert "create_hypertable('industrial_events', 'time'" in sql
    assert "create_hypertable('processed_events', 'time'" in sql
    assert "create_hypertable('ai_enriched', 'time'" in sql
    assert "create_hypertable('dead_letter_events', 'time'" in sql


def test_timescale_restore_sql_empty_tables_only_bootstraps_extension():
    sql = hb._timescale_restore_sql([])
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE" in sql
    assert "SELECT timescaledb_post_restore()" in sql
    assert "create_hypertable(" not in sql


def test_restore_backup_rehydrates_timescale_hypertables(monkeypatch, tmp_path):
    backup_path = tmp_path / "historian_backup_20260630_120000.sql"
    backup_path.write_bytes(b"test")
    monkeypatch.setattr(
        hb,
        "_connection_params",
        lambda: {"host": "localhost", "port": "5432", "database": "stream_engine", "user": "stream", "password": "stream"},
    )
    calls: list[list[str]] = []
    hypertable_checks = {"count": 0}

    def fake_run(command, **kwargs):
        calls.append(list(command))
        if command[:2] == ["pg_restore", "--list"]:
            return type("Result", (), {"stdout": "1; 10 20 TABLE - industrial_events\n2; 10 20 TABLE - processed_events\n3; 10 20 TABLE - ai_enriched\n4; 10 20 TABLE - dead_letter_events\n", "stderr": "", "returncode": 0})()
        if command[:1] == ["pg_restore"]:
            return type("Result", (), {"stdout": "restored\n", "stderr": "", "returncode": 0})()
        if command[:1] == ["psql"]:
            sql = command[-1]
            if "timescaledb_information.hypertables" in sql:
                hypertable_checks["count"] += 1
                if hypertable_checks["count"] == 1:
                    return type("Result", (), {"stdout": "", "stderr": "", "returncode": 0})()
                return type("Result", (), {"stdout": "industrial_events\nprocessed_events\nai_enriched\ndead_letter_events\n", "stderr": "", "returncode": 0})()
            return type("Result", (), {"stdout": "bootstrap ok\n", "stderr": "", "returncode": 0})()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(hb.subprocess, "run", fake_run)
    result = hb.restore_backup(str(backup_path), "restore_db")
    assert result["status"] == "success"
    assert result["hypertables_verified"] is True
    assert result["hypertables"]["matched"] is True
    assert any("timescaledb_post_restore" in " ".join(call) for call in calls)
    assert any("create_hypertable('industrial_events'" in " ".join(call) for call in calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
