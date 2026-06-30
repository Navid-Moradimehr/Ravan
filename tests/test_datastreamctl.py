"""Tests for the Phase 8 control CLI surface."""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from services.cli import datastreamctl as ctl
from services.datasets.runtime_catalog import (
    DATASET_SOURCES,
    get_dataset_source,
    list_dataset_sources,
)


class TestRuntimeCatalog:
    def test_lists_all_sources(self):
        assert len(list_dataset_sources()) == len(DATASET_SOURCES)

    def test_filters_by_category(self):
        synthetic = list_dataset_sources("synthetic")
        assert all(s.category == "synthetic" for s in synthetic)
        assert any(s.dataset_id == "ai4i" for s in synthetic)

    def test_get_known(self):
        assert get_dataset_source("ai4i") is not None
        assert get_dataset_source("ai4i").name.startswith("AI4I")

    def test_get_benchmark_pack(self):
        benchmark = get_dataset_source("industrial-benchmark")
        assert benchmark is not None
        assert benchmark.category == "benchmark"

    def test_get_unknown(self):
        assert get_dataset_source("nope") is None

    def test_mock_is_unlicensed(self):
        assert get_dataset_source("mock").licensed is False


class TestDatastreamctl:
    def _run(self, argv):
        buf = io.StringIO()
        rc = 0
        with redirect_stdout(buf):
            rc = ctl.main(argv)
        return rc, buf.getvalue()

    def test_datasets_command_lists_entries(self):
        rc, out = self._run(["datasets"])
        assert rc == 0
        assert "AI4I" in out
        assert "SWaT" in out

    def test_datasets_category_filter(self):
        rc, out = self._run(["datasets", "--category", "security"])
        assert rc == 0
        assert "SWaT" in out
        assert "WADI" in out
        assert "AI4I" not in out

    def test_scenarios_command_runs(self):
        rc, out = self._run(["scenarios"])
        assert rc == 0
        assert "normal" in out

    def test_doctor_runs_without_network(self):
        rc, _ = self._run(["--api-base", "http://127.0.0.1:9", "--ai-base", "http://127.0.0.1:9", "doctor"])
        assert rc in (0, 2)

    def test_config_command_runs(self):
        rc, out = self._run(["config"])
        assert rc == 0
        assert "DATASTREAM_API_BASE" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
