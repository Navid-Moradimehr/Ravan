from __future__ import annotations

import asyncio
import json

import httpx

from services.ai_gateway.config import Settings
from services.ai_gateway.providers import LLMProviderClient, build_fallback_summary, build_industrial_prompt
from services.common.structured_output import validate_industrial_summary


def test_legacy_aliases_map_to_llm_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.invalid/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "alias-key")
    monkeypatch.setenv("OPENAI_MODEL", "alias-model")
    settings = Settings()
    assert settings.llm_endpoint_url == "http://example.invalid/v1"
    assert settings.llm_api_key == "alias-key"
    assert settings.llm_model_id == "alias-model"
    assert settings.openai_base_url == "http://example.invalid/v1"


def test_openai_compat_request_spec_uses_chat_completions():
    settings = Settings(
        llm_provider="openai_compat",
        llm_endpoint_url="http://localhost:1234/v1",
        llm_api_key="test-key",
        llm_model_id="test-model",
    )
    client = LLMProviderClient(settings)
    spec = client.request_spec(build_industrial_prompt([{"asset_id": "Pump-01", "severity": "critical"}]))
    assert spec.url == "http://localhost:1234/v1/chat/completions"
    assert spec.headers["Authorization"] == "Bearer test-key"
    assert spec.body["model"] == "test-model"
    assert "messages" in spec.body


def test_ollama_request_spec_uses_api_chat():
    settings = Settings(
        llm_provider="ollama",
        llm_endpoint_url="http://localhost:11434",
        llm_model_id="mistral",
    )
    client = LLMProviderClient(settings)
    spec = client.request_spec("Hello")
    assert spec.url == "http://localhost:11434/api/chat"
    assert spec.body["stream"] is False
    assert spec.body["model"] == "mistral"


def test_response_parsers_handle_openai_and_ollama_shapes():
    settings = Settings()
    client = LLMProviderClient(settings)
    assert client.extract_content({"choices": [{"message": {"content": "ok"}}]}) == "ok"
    client = LLMProviderClient(Settings(llm_provider="ollama"))
    assert client.extract_content({"message": {"content": "ollama-ok"}}) == "ollama-ok"


def test_fallback_summary_is_deterministic():
    batch = [
        {"device_id": "Pump-01", "severity": "critical"},
        {"device_id": "Pump-02", "severity": "warning"},
    ]
    summary = build_fallback_summary(batch, "mock-error")
    payload = json.loads(summary)
    assert payload["mode"] == "deterministic_fallback"
    assert payload["critical_count"] == 1
    assert payload["warning_count"] == 1
    valid, errors, parsed = validate_industrial_summary(summary)
    assert valid is True
    assert errors == []
    assert parsed is not None


def test_build_industrial_prompt_uses_structured_contract():
    prompt = build_industrial_prompt([{"asset_id": "Pump-01", "severity": "critical"}])
    assert "critical_devices" in prompt
    assert "severity_counts" in prompt


def test_ai_gateway_enrich_batch_falls_back_on_invalid_json(monkeypatch):
    import services.ai_gateway.main as gateway

    async def fake_summarize(prompt: str, timeout_seconds: int, client=None) -> str:
        return "not-json"

    captured: dict[str, object] = {}

    class DummyProducer:
        def produce(self, topic, value):
            captured["topic"] = topic
            captured["payload"] = json.loads(value.decode("utf-8"))

        def poll(self, timeout):
            captured["polled"] = True

    monkeypatch.setattr(gateway.llm_client, "summarize", fake_summarize)
    gateway.service_state.mark_ok()

    asyncio.run(
        gateway.enrich_batch(
            [
                {"device_id": "Pump-01", "severity": "critical"},
                {"device_id": "Pump-02", "severity": "warning"},
            ],
            DummyProducer(),
        )
    )

    assert captured["topic"] == gateway.settings.ai_enriched_topic
    assert captured["payload"]["summary"]
    assert captured["payload"]["summary"].count("deterministic_fallback") == 1
    assert captured["payload"]["event_type"] == "ai.summary.generated"
    assert captured["payload"]["event_version"] == 1
    assert captured["payload"]["source_event_ids"]
    assert gateway.service_state.last_error.startswith("LLM fallback active")
