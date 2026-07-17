from __future__ import annotations

import asyncio
import json

import httpx

from services.ai_gateway.config import Settings
from services.ai_gateway.providers import LLMProviderClient, build_fallback_summary, build_industrial_prompt, provider_catalog
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


def test_anthropic_request_spec_uses_messages_contract():
    settings = Settings(llm_provider="anthropic", llm_api_key="anthropic-key", llm_model_id="claude-test")
    spec = LLMProviderClient(settings).request_spec("Inspect pump")
    assert spec.url == "https://api.anthropic.com/v1/messages"
    assert spec.headers["x-api-key"] == "anthropic-key"
    assert spec.headers["anthropic-version"] == "2023-06-01"
    assert spec.body["max_tokens"] == 2048
    assert spec.body["messages"][0]["role"] == "user"


def test_gemini_request_spec_uses_generate_content_contract():
    settings = Settings(llm_provider="gemini", llm_api_key="gemini-key", llm_model_id="gemini-test")
    spec = LLMProviderClient(settings).request_spec("Inspect pump")
    assert spec.url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    assert spec.headers["x-goog-api-key"] == "gemini-key"
    assert spec.body["contents"][0]["parts"][0]["text"] == "Inspect pump"


def test_openai_compatible_cloud_presets_use_override_and_parse_native_shapes():
    settings = Settings(llm_provider="deepseek", llm_endpoint_url="https://gateway.example/v1", llm_api_key="key")
    spec = LLMProviderClient(settings).request_spec("Inspect pump")
    assert spec.url == "https://gateway.example/v1/chat/completions"
    assert spec.headers["Authorization"] == "Bearer key"
    assert LLMProviderClient(Settings(llm_provider="anthropic")).extract_content({"content": [{"type": "text", "text": "report"}]}) == "report"
    assert LLMProviderClient(Settings(llm_provider="gemini")).extract_content({"candidates": [{"content": {"parts": [{"text": "report"}]}}]}) == "report"


def test_provider_catalog_does_not_contain_credentials():
    catalog = provider_catalog()
    ids = {item["id"] for item in catalog}
    assert {"anthropic", "gemini", "deepseek", "qwen", "kimi", "glm"}.issubset(ids)
    assert all("key" not in item and "secret" not in item for item in catalog)


def test_structured_schema_is_mapped_to_provider_native_contracts():
    schema = {"type": "object", "required": ["headline"], "properties": {"headline": {"type": "string"}}}
    openai = LLMProviderClient(Settings(llm_provider="openai_compat", llm_endpoint_url="http://localhost:1234/v1")).request_spec("JSON report", output_schema=schema)
    anthropic = LLMProviderClient(Settings(llm_provider="anthropic")).request_spec("JSON report", output_schema=schema)
    gemini = LLMProviderClient(Settings(llm_provider="gemini")).request_spec("JSON report", output_schema=schema)
    ollama = LLMProviderClient(Settings(llm_provider="ollama", llm_endpoint_url="http://localhost:11434")).request_spec("JSON report", output_schema=schema)
    assert openai.body["response_format"]["json_schema"]["schema"] == schema
    assert anthropic.body["output_config"]["format"]["schema"] == schema
    assert anthropic.body["system"][0]["cache_control"]["type"] == "ephemeral"
    assert gemini.body["generationConfig"]["responseJsonSchema"] == schema
    assert ollama.body["format"] == schema


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

    async def fake_summarize(prompt: str, *, output_schema, timeout_seconds: int, cache_mode="auto"):
        return "not-json", {"structured_mode": "guided", "cache_mode": cache_mode}

    captured: dict[str, object] = {}

    class DummyProducer:
        def produce(self, topic, key=None, value=None, on_delivery=None):
            captured["topic"] = topic
            captured["key"] = key
            captured["payload"] = json.loads(value.decode("utf-8"))

        def poll(self, timeout):
            captured["polled"] = True

    monkeypatch.setattr(gateway.llm_client, "summarize_structured", fake_summarize)
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
    assert captured["key"] == captured["payload"]["event_id"]
    assert captured["payload"]["summary"]
    assert captured["payload"]["structured_report"]["situation_status"] == "critical"
    assert captured["payload"]["used_fallback"] is True
    assert captured["payload"]["generation_metadata"]["structured_mode"] == "guided"
    assert captured["payload"]["generation_metadata"]["provider_response_received"] is True
    assert captured["payload"]["generation_metadata"]["used_fallback"] is True
    assert "output_validation_failed" in captured["payload"]["generation_metadata"]["generation_error"]
    assert captured["payload"]["event_type"] == "ai.summary.generated"
    assert captured["payload"]["event_version"] == 1
    assert captured["payload"]["source_event_ids"]
    assert gateway.service_state.last_error.startswith("LLM fallback active")
