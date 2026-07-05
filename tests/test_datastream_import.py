"""Tests for the datastream-import dataset tooling."""
from __future__ import annotations

import io
import textwrap
import zipfile
from xml.sax.saxutils import escape
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
            assert s.format in {"csv", "zip", "xlsx"}

    def test_source_by_id_lookup(self):
        assert imp.SOURCE_BY_ID["ai4i"].source_id == "ai4i"
        assert imp.SOURCE_BY_ID.get("nope") is None


class TestImportCommands:
    def _make_minimal_xlsx(self, path: Path, rows: list[list[str]]) -> None:
        def cell_ref(col_idx: int, row_idx: int) -> str:
            col = ""
            idx = col_idx + 1
            while idx:
                idx, rem = divmod(idx - 1, 26)
                col = chr(65 + rem) + col
            return f"{col}{row_idx}"

        def row_xml(values: list[str], row_idx: int) -> str:
            cells = []
            for idx, value in enumerate(values):
                ref = cell_ref(idx, row_idx)
                if row_idx == 1:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
                else:
                    cells.append(f'<c r="{ref}"><v>{escape(value)}</v></c>')
            return f'<row r="{row_idx}">{"".join(cells)}</row>'

        sheet_rows = "".join(row_xml(row, idx + 1) for idx, row in enumerate(rows))
        sheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{sheet_rows}</sheetData>
</worksheet>"""
        workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
        rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
        root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("[Content_Types].xml", content_types)
            zf.writestr("_rels/.rels", root_rels)
            zf.writestr("xl/workbook.xml", workbook_xml)
            zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
            zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

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

    def test_fetch_ai4i_zip_extracts_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr(imp, "DEFAULT_DATA_DIR", tmp_path)

        def fake_download(url, dest, timeout=30.0):
            with zipfile.ZipFile(dest, "w") as zf:
                zf.writestr(
                    "ai4i2020.csv",
                    textwrap.dedent("""\
                        UDI,Product ID,Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],Torque [Nm],Tool wear [min],Machine failure,TWF,HDF,PWF,OSF,RNF
                        1,L1,M,300,310,1500,40,10,0,0,0,0,0,0
                    """),
                )

        monkeypatch.setattr(imp, "_http_download", fake_download)
        rc, out = self._run(["fetch", "ai4i", "--force"])
        assert rc == 0
        staged = tmp_path / "ai4i2020.csv"
        assert staged.exists()
        assert staged.read_text(encoding="utf-8").startswith("UDI,Product ID")
        assert "staged CSV" in out or "extracted CSVs" in out

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

    def test_convert_cmapss_zip_creates_benchmark_csv(self, tmp_path):
        input_path = tmp_path / "cmapss.zip"
        with zipfile.ZipFile(input_path, "w") as zf:
            zf.writestr(
                "train_FD001.txt",
                "1 1 0.1 0.2 0.3 " + " ".join(str(idx) for idx in range(1, 22)),
            )
        output_path = tmp_path / "cmapss-zip-out.csv"
        rc, out = self._run(["convert", str(input_path), str(output_path), "--preset", "cmapss", "--site-id", "plant-a", "--line", "line-01", "--source-prefix", "cmapss"])
        assert rc == 0
        assert output_path.exists()
        assert "converted preset=cmapss" in out
        content = output_path.read_text(encoding="utf-8")
        assert "S1" in content
        assert "plant-a" in content

    def test_convert_swat_xlsx_creates_benchmark_csv(self, tmp_path):
        input_path = tmp_path / "swat.xlsx"
        self._make_minimal_xlsx(
            input_path,
            [
                ["Timestamp", "Label", "FIT101", "LIT101"],
                ["2026-07-01T00:00:00Z", "normal", "1.5", "2.5"],
                ["2026-07-01T00:00:01Z", "attack", "1.8", "2.7"],
            ],
        )
        output_path = tmp_path / "swat-out.csv"
        rc, out = self._run(["convert", str(input_path), str(output_path), "--preset", "swat", "--site-id", "plant-a", "--line", "line-01", "--source-prefix", "swat"])
        assert rc == 0
        assert output_path.exists()
        assert "converted preset=swat" in out
        content = output_path.read_text(encoding="utf-8")
        assert "FIT101" in content
        assert "attack" in content

    def test_fetch_swat_extract_skips_non_zip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(imp, "DEFAULT_DATA_DIR", tmp_path)

        def fake_download(url, dest, timeout=30.0):
            Path(dest).write_bytes(b"not-a-zip")

        monkeypatch.setattr(imp, "_http_download", fake_download)
        rc, out = self._run(["fetch", "swat", "--force", "--extract"])
        assert rc == 0
        assert "not a zip archive" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
