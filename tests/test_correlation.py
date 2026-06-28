"""Tests for correlation analysis."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "analytics"))

from correlation import CorrelationAnalyzer


@pytest.fixture
def analyzer():
    return CorrelationAnalyzer(window_size=100)


def test_add_value(analyzer):
    analyzer.add_value("PUMP-01.Temperature", "2024-01-01T00:00:00Z", 50.0)
    assert "PUMP-01.Temperature" in analyzer._data
    assert len(analyzer._data["PUMP-01.Temperature"]) == 1


def test_pearson_correlation(analyzer):
    # Perfect positive correlation
    x = [1, 2, 3, 4, 5]
    y = [2, 4, 6, 8, 10]
    corr = analyzer._pearson_correlation(x, y)
    assert round(corr, 4) == 1.0

    # Perfect negative correlation
    y = [10, 8, 6, 4, 2]
    corr = analyzer._pearson_correlation(x, y)
    assert round(corr, 4) == -1.0

    # No correlation
    y = [5, 5, 5, 5, 5]
    corr = analyzer._pearson_correlation(x, y)
    assert corr == 0.0


def test_correlation_matrix(analyzer):
    # Add correlated data
    for i in range(10):
        ts = f"2024-01-01T00:00:{i:02d}Z"
        analyzer.add_value("TagA", ts, 50.0 + i * 2)
        analyzer.add_value("TagB", ts, 100.0 + i * 4)
        analyzer.add_value("TagC", ts, 50.0 - i * 2)

    matrix = analyzer.get_correlation_matrix()
    assert "TagA" in matrix
    assert "TagB" in matrix

    # TagA and TagB should be positively correlated
    if "TagB" in matrix.get("TagA", {}):
        assert matrix["TagA"]["TagB"] > 0.9


def test_find_strong_correlations(analyzer):
    for i in range(20):
        ts = f"2024-01-01T00:00:{i:02d}Z"
        analyzer.add_value("TagA", ts, 50.0 + i * 2)
        analyzer.add_value("TagB", ts, 100.0 + i * 4)
        analyzer.add_value("TagC", ts, 50.0 - i * 2)

    strong = analyzer.find_strong_correlations(threshold=0.7)
    assert len(strong) > 0

    # Should find TagA-TagB positive correlation
    tag_pairs = [(s["tag1"], s["tag2"]) for s in strong]
    assert ("TagA", "TagB") in tag_pairs or ("TagB", "TagA") in tag_pairs


def test_detect_anomaly_propagation(analyzer):
    for i in range(10):
        ts = f"2024-01-01T00:00:{i:02d}Z"
        analyzer.add_value("AnomalyTag", ts, 50.0 + i * 5)
        analyzer.add_value("RelatedTag", ts, 100.0 + i * 5)
        analyzer.add_value("UnrelatedTag", ts, 25.0)

    propagation = analyzer.detect_anomaly_propagation("AnomalyTag", lookback=10)
    assert len(propagation) > 0

    # RelatedTag should have high correlation
    related = next((p for p in propagation if p["tag"] == "RelatedTag"), None)
    assert related is not None
    assert related["correlation"] > 0.5
