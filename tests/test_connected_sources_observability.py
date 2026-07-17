from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_source_throughput_metric_is_emitted_with_connection_labels():
    publisher = (ROOT / "services" / "edge_ingest" / "publisher.py").read_text(encoding="utf-8")
    assert 'edge_ingest_source_events_total' in publisher
    assert 'connection_id", "protocol", "site"' in publisher
    assert 'event.source_connection_id or event.source_id' in publisher


def test_connected_sources_dashboard_is_valid_and_label_driven():
    path = ROOT / "docker" / "grafana" / "dashboards" / "connected-sources.json"
    dashboard = json.loads(path.read_text(encoding="utf-8"))
    assert dashboard["uid"] == "connected-sources"
    assert {item["name"] for item in dashboard["templating"]["list"]} == {"site", "connection_id"}
    expressions = [
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    ]
    assert any("edge_ingest_source_events_total" in expr for expr in expressions)
    assert any("edge_source_state" in expr for expr in expressions)


def test_grafana_provisions_all_dashboard_files():
    provisioning = (ROOT / "docker" / "grafana" / "provisioning" / "dashboards" / "ravan.yml").read_text(encoding="utf-8")
    assert "/var/lib/grafana/dashboards" in provisioning
