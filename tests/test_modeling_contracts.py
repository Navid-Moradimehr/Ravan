from __future__ import annotations

import json
from pathlib import Path

from services.common.agent_tools import build_context_package, tool_registry
from services.common.modeling import ModelRegistry
from services.common.prompt_registry import prompt_registry
from services.common.structured_output import validate_industrial_summary


def test_model_registry_exports_roles():
    registry = ModelRegistry.from_env()
    export = registry.export()
    roles = {entry["role"] for entry in export["roles"]}
    assert {"summarization", "embeddings", "retrieval"} <= roles
    assert any(entry["role"] == "diagnostic_agent_readonly" and entry["enabled"] is False for entry in export["roles"])


def test_prompt_registry_renders_industrial_prompt():
    prompt = prompt_registry.render("industrial-summary-v1", batch_json="[]")
    assert "valid JSON" in prompt
    assert "critical_devices" in prompt


def test_structured_output_validation_accepts_expected_shape():
    payload = json.dumps(
        {
            "summary": "ok",
            "critical_devices": ["Pump-01"],
            "warning_devices": ["Pump-02"],
            "probable_causes": ["threshold breach"],
            "recommended_actions": ["inspect"],
            "batch_size": 2,
            "severity_counts": {"critical": 1, "warning": 1, "normal": 0},
        }
    )
    valid, errors, parsed = validate_industrial_summary(payload)
    assert valid is True
    assert errors == []
    assert parsed is not None
    assert parsed["batch_size"] == 2


def test_tool_registry_exposes_read_only_tools():
    tools = tool_registry.list_tools()
    assert any(tool["name"] == "historian.recent_events" and tool["read_only"] for tool in tools)
    assert all(tool["read_only"] for tool in tools)


def test_context_builder_uses_injected_data(monkeypatch, tmp_path):
    import services.common.agent_tools as agent_tools

    monkeypatch.setattr(agent_tools, "query_alarms", lambda limit: [{"severity": "warning", "asset_id": "Pump-01"}])
    monkeypatch.setattr(agent_tools, "query_recent_events", lambda table, limit: [{"table": table, "limit": limit}])
    monkeypatch.setattr(agent_tools, "query_trend", lambda asset_id, tag, hours: [{"asset_id": asset_id, "tag": tag, "hours": hours}])
    monkeypatch.setattr(agent_tools, "list_scenarios", lambda: [{"scenario_id": "normal"}])
    monkeypatch.setattr(agent_tools.report_engine, "list_templates", lambda: [{"template_id": "daily"}])
    monkeypatch.setattr(
        agent_tools,
        "load_hierarchy",
        lambda path: {"assets": [{"id": "plant-01", "name": "Plant 01", "type": "site", "children": []}]},
    )
    monkeypatch.setattr(agent_tools, "hierarchy_to_tree", lambda hierarchy: hierarchy["assets"])

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
schema_version: 1
profile_id: demo
deployment_mode: single-site
site:
  id: demo-site
  name: Demo Site
  region: test
  network_zone: ops
runtime:
  image_tag: latest
  redpanda_brokers: localhost:9092
  historian_backend: timescaledb
  ai:
    provider: openai_compat
    endpoint_url: http://localhost:1234/v1
    model_id: demo-model
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

    context = build_context_package(asset_id="Pump-01", tag="Temperature", site_profile_path=profile_path)
    assert context["scope"]["asset_id"] == "Pump-01"
    assert context["trend"][0]["tag"] == "Temperature"
    assert context["site_profile"]["profile_id"] == "demo"
    assert context["model_roles"]["validation_errors"] == []
