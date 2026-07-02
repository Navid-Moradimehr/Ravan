"""Tests for the datastream-import dataset tooling."""
from __future__ import annotations

import io
import textwrap
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from services.cli import datastream_import as imp


class TestImportSources:
    def test_known_sources_present(self):
        ids = {s.source_id for s in imp.SOURCES}
        assert {"ai4i", "cmapss", "nab", "skab"} <= ids

    def test_each_source_has_download_metadata(self):
        for s in imp.SOURCES:
            assert s.url.startswith("http"), s
            assert s.filename
            assert s.format in {"csv", "zip"}

    def test_source_by_id_lookup(self):
        assert imp.SOURCE_BY_ID["ai4i"].source_id == "ai4i"
        assert imp.SOURCE_BY_ID.get("nope") is None


class TestImportCommands:
    def _run(self, argv):
        buf = io.StringIO()
        rc = 0
        with redirect_stdout(buf):
            rc = imp.main(argv)
        return rc, buf.getvalue()

    def test_list_runs(self):
        rc, out = self._run(["list"])
        assert rc == 0
        assert "AI4I" in out
        assert "C-MAPSS" in out

    def test_info_known(self):
        rc, out = self._run(["info", "ai4i"])
        assert rc == 0
        assert "AI4I 2020" in out
        assert "CC BY 4.0" in out

    def test_info_unknown_returns_error(self):
        rc, _ = self._run(["info", "nope"])
        assert rc == 2

    def test_fetch_local_stages_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(imp, "DEFAULT_DATA_DIR", tmp_path)
        src = tmp_path / "src.csv"
        src.write_text("a,b\n1,2\n")
        rc, out = self._run(["fetch", "ai4i", "--local", str(src)])
        assert rc == 0
        staged = tmp_path / "ai4i2020.csv"
        assert staged.exists()
        assert "staged from local" in out

    def test_fetch_skips_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(imp, "DEFAULT_DATA_DIR", tmp_path)
        (tmp_path / "ai4i2020.csv").write_text("x")
        rc, out = self._run(["fetch", "ai4i"])
        assert rc == 0
        assert "already present" in out

    def test_status_runs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(imp, "DEFAULT_DATA_DIR", tmp_path)
        (tmp_path / "ai4i2020.csv").write_text("present")
        rc, out = self._run(["status"])
        assert rc == 0
        assert "present=1/4" in out or "present=1/" in out

    def test_validate_ai4i_good(self, tmp_path):
        csv_path = tmp_path / "ai4i.csv"
        csv_path.write_text(textwrap.dedent("""\
            UDI,Product ID,Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure,TWF,HDF,PWF,OSF,RNF
            1,L1,M,300,310,1500,40,10,0,0,0,0,0,0
        """))
        rc, out = self._run(["validate", str(csv_path), "--format", "ai4i"])
        assert rc == 0
        assert "OK" in out

    def test_validate_missing_file(self, tmp_path):
        rc, out = self._run(["validate", str(tmp_path / "missing.csv"), "--format", "ai4i"])
        assert rc == 1

    def test_convert_ai4i_creates_benchmark_csv(self, tmp_path):
        input_path = tmp_path / "ai4i.csv"
        input_path.write_text(textwrap.dedent("""\
            UDI,Product ID,Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure,TWF,HDF,PWF,OSF,RNF
            1,L1,M,300,310,1500,40,10,0,0,0,0,0,0
        """))
        output_path = tmp_path / "benchmark.csv"
        rc, out = self._run(["convert", str(input_path), str(output_path), "--preset", "ai4i", "--site-id", "plant-a", "--line", "line-02", "--source-prefix", "ai4i"])
        assert rc == 0
        assert output_path.exists()
        assert "converted preset=ai4i" in out
        content = output_path.read_text(encoding="utf-8")
        assert "site,line,ts_source" in content
        assert "plant-a" in content

    def test_convert_generic_creates_benchmark_csv(self, tmp_path):
        input_path = tmp_path / "generic.csv"
        input_path.write_text(textwrap.dedent("""\
            asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step
            Pump-01,Temperature,55.1,good,c,plant-a,line-01,2026-07-01T00:00:00Z,1,normal,normal,normal,0
        """))
        output_path = tmp_path / "generic-out.csv"
        rc, out = self._run(["convert", str(input_path), str(output_path), "--preset", "generic", "--site-id", "plant-a", "--line", "line-01", "--source-prefix", "generic"])
        assert rc == 0
        assert output_path.exists()
        assert "converted preset=generic" in out
        assert "Pump-01" in output_path.read_text(encoding="utf-8")

    def test_convert_cmapss_creates_benchmark_csv(self, tmp_path):
        input_path = tmp_path / "cmapss.csv"
        input_path.write_text(textwrap.dedent("""\
            unit,cycle,setting1,setting2,setting3,s1,s2,s3
            1,1,0.1,0.2,0.3,10,20,30
        """))
        output_path = tmp_path / "cmapss-out.csv"
        rc, out = self._run(["convert", str(input_path), str(output_path), "--preset", "cmapss", "--site-id", "plant-a", "--line", "line-01", "--source-prefix", "cmapss"])
        assert rc == 0
        assert output_path.exists()
        assert "converted preset=cmapss" in out
        content = output_path.read_text(encoding="utf-8")
        assert "S1" in content
        assert "plant-a" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
