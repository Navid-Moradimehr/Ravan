from __future__ import annotations

from fastapi.testclient import TestClient


def test_site_observability_snapshot_uses_health_and_backup(monkeypatch, tmp_path) -> None:
    import services.common.site_observability as obs

    monkeypatch.setattr(obs, "probe_kafka", lambda: True)
    monkeypatch.setattr(obs, "probe_historian", lambda: True)
    monkeypatch.setattr(obs, "probe_ai_gateway", lambda: False)
    monkeypatch.setattr(obs, "get_walg_status", lambda: {"installed": True})
    monkeypatch.setattr(obs, "_prometheus_query", lambda _query: 0.0)

    profile_path = tmp_path / "site.yaml"
    profile_path.write_text(
        """
schema_version: 1
profile_id: demo
deployment_mode: plant-local
site:
  id: demo-site
  name: Demo Site
  region: test
  network_zone: ops
runtime:
  image_tag: latest
  kafka_brokers: localhost:9092
  historian_backend: timescaledb
  ai:
    provider: disabled
    endpoint_url: ""
    model_id: ""
    local_only: true
backups:
  directory: backups
  schedule: daily
  retention_days: 7
federation:
  enabled: false
  export_mode: none
        """.strip(),
        encoding="utf-8",
    )

    snapshot = obs.build_site_observability_snapshot(site_profile_path=profile_path)

    assert snapshot["plane"] == "site-observability"
    assert snapshot["deployment_mode"] == "plant-local"
    assert snapshot["slo_targets"]["ingest_availability_percent"] == 99.5
    assert snapshot["availability"]["broker_health"] is True
    assert snapshot["availability"]["ai_gateway_health"] is False
    assert snapshot["availability"]["backup_tooling_ready"] is True
    assert snapshot["signals"]
    assert "processing lag" in snapshot["baseline_signals"]


def test_site_observability_api_route_returns_snapshot(monkeypatch) -> None:
    import services.common.site_observability as obs
    from services.api_service.main import app

    monkeypatch.setattr(obs, "probe_kafka", lambda: True)
    monkeypatch.setattr(obs, "probe_historian", lambda: True)
    monkeypatch.setattr(obs, "probe_ai_gateway", lambda: True)
    monkeypatch.setattr(obs, "get_walg_status", lambda: {"installed": False})
    monkeypatch.setattr(obs, "_prometheus_query", lambda _query: 0.0)

    client = TestClient(app)
    response = client.get("/api/v1/observability/site")

    assert response.status_code == 200
    body = response.json()
    assert body["plane"] == "site-observability"
    assert body["availability"]["historian_health"] is True


def test_slo_evaluation_marks_missing_prometheus_values_unknown(monkeypatch):
    import services.common.site_observability as obs

    monkeypatch.setattr(obs, "_prometheus_query", lambda _query: None)
    evaluation = obs._slo_evaluation()

    assert evaluation["status"] == "unknown"
    assert any(item["status"] == "unknown" for item in evaluation["measurements"])


def test_slo_evaluation_queries_fixed_evidence_set(monkeypatch):
    import services.common.site_observability as obs

    queries = []
    monkeypatch.setattr(obs, "_prometheus_query", lambda query: queries.append(query) or 0.0)

    evaluation = obs._slo_evaluation()

    assert evaluation["status"] == "passed"
    assert len(queries) == 5


def test_slo_evaluation_converts_probe_timeout_to_unknown(monkeypatch):
    import time
    import services.common.site_observability as obs

    def slow_probe(_query):
        time.sleep(3.0)
        return 0.0

    monkeypatch.setattr(obs, "_prometheus_query", slow_probe)

    evaluation = obs._slo_evaluation()

    assert evaluation["status"] == "unknown"
    assert any(item["status"] == "unknown" for item in evaluation["measurements"])
