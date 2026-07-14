from pathlib import Path


def test_trend_api_exposes_bounded_read_controls():
    source = Path("services/api_service/routers/historian.py").read_text(encoding="utf-8")
    assert "max_points: int = 2000" in source
    assert "aggregation: str = \"auto\"" in source


def test_trend_query_uses_timescale_bucket_for_dense_ranges():
    source = Path("services/historian/client.py").read_text(encoding="utf-8")
    assert "time_bucket" in source
    assert "max_points = max(1, min" in source
