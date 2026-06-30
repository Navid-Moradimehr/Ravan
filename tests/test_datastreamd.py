"""Tests for the datastreamd runtime supervisor."""
from __future__ import annotations

import io
import os
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from services.cli import datastreamd as d


class TestSupervisorSpecs:
    def test_specs_cover_core_services(self):
        names = {s.name for s in d.SERVICE_SPECS}
        assert {"api", "ai", "edge", "processor", "mock"} <= names

    def test_each_spec_has_module_and_description(self):
        for spec in d.SERVICE_SPECS:
            assert spec.module.startswith("services.")
            assert spec.description

    def test_resolve_order_respects_dependencies(self):
        d.SPEC_BY_NAME["testdep"] = d.ServiceSpec(
            name="testdep",
            module="x",
            description="x",
            health_url="",
            depends_on=("api",),
        )
        try:
            order = d._resolve_order(["testdep"])
            assert order.index("api") < order.index("testdep")
        finally:
            d.SPEC_BY_NAME.pop("testdep", None)

    def test_resolve_order_dedupes(self):
        order = d._resolve_order(["api", "ai", "api"])
        assert order.count("api") == 1


class TestSupervisorLifecycle:
    def test_pid_file_isolated_per_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(d, "PID_DIR", tmp_path)
        monkeypatch.setattr(d, "PID_FILE", tmp_path / "processes.json")
        assert d._load_records() == {}
        rec = d.ProcRecord(name="api", pid=123, module="m", started_at=time.time(), health_url="")
        d._save_records({"api": rec})
        loaded = d._load_records()
        assert "api" in loaded and loaded["api"].pid == 123

    def test_is_alive_false_for_invalid_pid(self, monkeypatch):
        monkeypatch.setattr(d, "PID_DIR", Path(os.devnull))
        rec = d.ProcRecord(name="x", pid=9999999, module="m", started_at=0)
        assert d._is_alive(rec) is False

    def test_status_runs_without_processes(self, monkeypatch, tmp_path):
        monkeypatch.setattr(d, "PID_DIR", tmp_path)
        monkeypatch.setattr(d, "PID_FILE", tmp_path / "processes.json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = d.main(["status"])
        out = buf.getvalue()
        assert rc == 0
        assert "datastreamd managed services" in out
        for name in ("api", "ai", "edge", "processor", "mock"):
            assert name in out

    def test_down_with_nothing_running_is_clean(self, monkeypatch, tmp_path):
        monkeypatch.setattr(d, "PID_DIR", tmp_path)
        monkeypatch.setattr(d, "PID_FILE", tmp_path / "processes.json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = d.main(["down"])
        assert rc == 0

    def test_site_profile_context_loads_env(self):
        profile = Path(__file__).resolve().parents[1] / "config" / "site-profiles" / "single-site.yaml"
        env, meta = d._load_site_profile_context(str(profile))
        assert env["SITE_ID"] == "demo-site"
        assert meta["deployment_mode"] == "single-site"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
