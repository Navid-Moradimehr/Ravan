"""Tests for datastream-import dataset coverage."""
from __future__ import annotations

from services.cli.datastream_import import SOURCES, SOURCE_BY_ID


def test_all_expected_datasets_present():
    ids = {s.source_id for s in SOURCES}
    assert "ai4i" in ids
    assert "cmapss" in ids
    assert "nab" in ids
    assert "skab" in ids
    assert "nasa-bearing" in ids
    assert "swat" in ids


def test_nasa_bearing_source_config():
    src = SOURCE_BY_ID["nasa-bearing"]
    assert src.format == "zip"
    assert "nasa" in src.license_note.lower()


def test_swat_source_config():
    src = SOURCE_BY_ID["swat"]
    assert src.format == "xlsx" or src.format == "zip"
    assert "academic" in src.license_note.lower() or "registration" in src.license_note.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
