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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
