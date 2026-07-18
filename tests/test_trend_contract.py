from pathlib import Path


def test_trend_api_exposes_bounded_read_controls():
    source = Path("services/api_service/routers/historian.py").read_text(encoding="utf-8")
    assert "max_points: int = 2000" in source
    assert "aggregation: str = \"auto\"" in source


def test_trend_query_uses_timescale_bucket_for_dense_ranges():
    source = Path("services/historian/client.py").read_text(encoding="utf-8")
    assert "time_bucket" in source
    assert "max_points = max(1, min" in source


def test_trend_contract_supports_optional_site_scoping():
    route = Path("services/api_service/routers/historian.py").read_text(encoding="utf-8")
    client = Path("services/historian/client.py").read_text(encoding="utf-8")
    ui_api = Path("ui/lib/api.ts").read_text(encoding="utf-8")

    assert "site_id: str | None = None" in route
    assert "site_id=site_id" in route
    assert "site_id: str | None = None" in client
    assert "AND site = %s" in client
    assert "siteId?: string" in ui_api
