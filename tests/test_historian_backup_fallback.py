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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
