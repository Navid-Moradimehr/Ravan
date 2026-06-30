from __future__ import annotations

import json

import httpx

from services.ai_gateway.config import Settings
from services.ai_gateway.providers import LLMProviderClient, build_fallback_summary, build_industrial_prompt


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
