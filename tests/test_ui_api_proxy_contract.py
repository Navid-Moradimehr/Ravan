from pathlib import Path


UI_API = Path(__file__).resolve().parents[1] / "ui" / "app" / "api"


def test_dashboard_proxies_every_mutating_ui_surface_used_by_components():
    expected = [
        "query/route.ts",
        "kpis/route.ts",
        "kpis/[kpiId]/route.ts",
        "webhooks/test/[hookId]/route.ts",
        "connections/[connectionId]/route.ts",
        "connections/[connectionId]/[action]/route.ts",
    ]
    for relative in expected:
        assert (UI_API / relative).exists(), f"missing dashboard API proxy: {relative}"
