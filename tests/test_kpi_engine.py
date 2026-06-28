"""Tests for KPI engine."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "analytics"))

from kpi_engine import KPIEngine, KPIFormula


@pytest.fixture
def engine():
    return KPIEngine()


def test_register_kpi(engine):
    kpi = KPIFormula(
        kpi_id="test-kpi",
        name="Test KPI",
        input_tags=["TagA", "TagB"],
        expression="TagA + TagB",
    )
    engine.register_kpi(kpi)
    assert "test-kpi" in engine._kpis
    assert "TagA" in engine._data_windows


def test_unregister_kpi(engine):
    kpi = KPIFormula(kpi_id="test-kpi", name="Test", input_tags=["TagA"])
    engine.register_kpi(kpi)
    assert engine.unregister_kpi("test-kpi") is True
    assert engine.unregister_kpi("test-kpi") is False


def test_list_kpis(engine):
    kpi = KPIFormula(kpi_id="test-kpi", name="Test", input_tags=["TagA"])
    engine.register_kpi(kpi)
    kpis = engine.list_kpis()
    assert len(kpis) == 1
    assert kpis[0]["kpi_id"] == "test-kpi"


def test_safe_eval(engine):
    result = engine._safe_eval("2 + 3", {})
    assert result == 5

    result = engine._safe_eval("a + b", {"a": 10, "b": 20})
    assert result == 30

    result = engine._safe_eval("max(1, 2, 3)", {})
    assert result == 3

    # Invalid expression should return None
    result = engine._safe_eval("__import__('os')", {})
    assert result is None


def test_evaluate_kpi(engine):
    kpi = KPIFormula(
        kpi_id="test-kpi",
        name="Test KPI",
        input_tags=["TagA", "TagB"],
        expression="TagA + TagB",
        warning_threshold=15.0,
        critical_threshold=20.0,
    )
    engine.register_kpi(kpi)

    # Ingest values
    engine.ingest_value("TagA", 10.0)
    results = engine.ingest_value("TagB", 5.0)

    assert len(results) == 1
    assert results[0]["kpi_id"] == "test-kpi"
    assert results[0]["value"] == 15.0
    assert results[0]["severity"] == "warning"


def test_evaluate_kpi_critical(engine):
    kpi = KPIFormula(
        kpi_id="test-kpi",
        name="Test KPI",
        input_tags=["TagA"],
        expression="TagA * 2",
        critical_threshold=50.0,
    )
    engine.register_kpi(kpi)

    engine.ingest_value("TagA", 30.0)
    results = engine.ingest_value("TagA", 30.0)

    assert len(results) == 1
    assert results[0]["value"] == 60.0
    assert results[0]["severity"] == "critical"


def test_sample_kpis(engine):
    samples = engine.get_sample_kpis()
    assert len(samples) > 0
    assert any(k.kpi_id == "pump_efficiency" for k in samples)
