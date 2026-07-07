from __future__ import annotations

import json


def test_ai_summary_event_contract_contains_versioned_metadata():
    from services.common.ai_event_contract import build_ai_summary_event

    event = build_ai_summary_event(
        [
            {"event_id": "evt-1", "asset_id": "Pump-01", "site_id": "site-a", "topic": "iot.processed", "severity": "critical"},
            {"event_id": "evt-2", "asset_id": "Pump-02", "site_id": "site-a", "topic": "iot.processed", "severity": "warning"},
        ],
        summary='{"summary":"ok"}',
        provider="openai_compat",
        model_id="test-model",
        endpoint="http://localhost:1234/v1",
        prompt_version="1.0.0",
        used_fallback=True,
        latency_seconds=0.25,
    )

    assert event["event_type"] == "ai.summary.generated"
    assert event["event_version"] == 1
    assert event["topic"] == "iot.ai_enriched"
    assert event["category"] == "ai"
    assert event["model_version"] == "test-model"
    assert event["prompt_version"] == "1.0.0"
    assert event["source_event_ids"] == ["evt-1", "evt-2"]
    assert event["source_event_count"] == 2
    assert event["source_site_ids"] == ["site-a"]
    assert event["source_asset_ids"] == ["Pump-01", "Pump-02"]
    assert event["severity_counts"]["critical"] == 1
    assert event["used_fallback"] is True


def test_ai_summary_event_json_serializes():
    from services.common.ai_event_contract import build_ai_summary_event

    event = build_ai_summary_event([], summary="{}", provider="openai_compat", model_id="test-model", endpoint="http://localhost:1234/v1")
    payload = json.loads(json.dumps(event))
    assert payload["event_type"] == "ai.summary.generated"


def test_ai_summary_schema_is_registered():
    from services.common.schema_registry import schema_registry

    schema = schema_registry.get("ai_summary_event")
    assert schema is not None
    fields = {field["name"] for field in schema.fields}
    assert {"event_id", "event_type", "event_version", "source_event_ids", "summary"} <= fields
