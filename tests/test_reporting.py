"""Tests for report generation."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "analytics"))

from reporting import ReportEngine, ReportTemplate


@pytest.fixture
def engine(tmp_path):
    return ReportEngine(output_dir=str(tmp_path))


def test_register_template(engine):
    template = ReportTemplate(
        template_id="test-report",
        name="Test Report",
        query="SELECT * FROM industrial_events LIMIT 10",
        format="csv",
    )
    engine.register_template(template)
    assert "test-report" in engine._templates


def test_list_templates(engine):
    template = ReportTemplate(template_id="test", name="Test")
    engine.register_template(template)
    templates = engine.list_templates()
    assert len(templates) == 1
    assert templates[0]["template_id"] == "test"


def test_export_csv(engine, tmp_path):
    data = [
        {"asset_id": "PUMP-01", "tag": "Temperature", "value": 50.0},
        {"asset_id": "PUMP-01", "tag": "Pressure", "value": 7.0},
    ]
    filepath = tmp_path / "test.csv"
    engine._export_csv(data, filepath)
    assert filepath.exists()
    content = filepath.read_text()
    assert "asset_id" in content
    assert "PUMP-01" in content


def test_export_json(engine, tmp_path):
    data = [{"asset_id": "PUMP-01", "value": 50.0}]
    filepath = tmp_path / "test.json"
    engine._export_json(data, filepath)
    assert filepath.exists()
    content = filepath.read_text()
    assert "PUMP-01" in content


def test_default_templates(engine):
    templates = engine.get_default_templates()
    assert len(templates) >= 3
    assert any(t.template_id == "daily_alarms" for t in templates)
    assert any(t.template_id == "weekly_trends" for t in templates)


def test_list_generated_reports(engine, tmp_path):
    # Create a dummy report file
    (tmp_path / "report_20240101.csv").write_text("test")
    reports = engine.list_generated_reports()
    assert len(reports) == 1
    assert reports[0]["filename"] == "report_20240101.csv"
