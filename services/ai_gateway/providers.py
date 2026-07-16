from __future__ import annotations

import json
import ipaddress
from dataclasses import dataclass
from urllib.parse import quote, urlparse
from typing import Any

import httpx

from services.common.prompt_registry import build_industrial_prompt as render_industrial_prompt


@dataclass(frozen=True)
class LLMRequestSpec:
    url: str
    headers: dict[str, str]
    body: dict[str, Any]


class LLMProviderError(RuntimeError):
    pass


class LLMDisabledError(LLMProviderError):
    pass


# Providers with a native API use an adapter below. Providers whose public API
# is OpenAI-compatible intentionally share the existing request contract.
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {"canonical": "openai_compat", "base_url": "https://api.openai.com/v1", "auth": "bearer"},
    "openai_compat": {"canonical": "openai_compat", "auth": "bearer"},
    "anthropic": {"canonical": "anthropic", "base_url": "https://api.anthropic.com", "auth": "x-api-key"},
    "gemini": {"canonical": "gemini", "base_url": "https://generativelanguage.googleapis.com", "auth": "x-goog-api-key"},
    "google": {"canonical": "gemini", "base_url": "https://generativelanguage.googleapis.com", "auth": "x-goog-api-key"},
    "google_gemini": {"canonical": "gemini", "base_url": "https://generativelanguage.googleapis.com", "auth": "x-goog-api-key"},
    "deepseek": {"canonical": "openai_compat", "base_url": "https://api.deepseek.com", "auth": "bearer"},
    "qwen": {"canonical": "openai_compat", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "auth": "bearer"},
    "dashscope": {"canonical": "openai_compat", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "auth": "bearer"},
    "kimi": {"canonical": "openai_compat", "base_url": "https://api.moonshot.ai/v1", "auth": "bearer"},
    "moonshot": {"canonical": "openai_compat", "base_url": "https://api.moonshot.ai/v1", "auth": "bearer"},
    "glm": {"canonical": "openai_compat", "base_url": "https://open.bigmodel.cn/api/paas/v4", "auth": "bearer"},
    "zhipu": {"canonical": "openai_compat", "base_url": "https://open.bigmodel.cn/api/paas/v4", "auth": "bearer"},
    "ollama": {"canonical": "ollama", "auth": "none"},
}


def provider_catalog() -> list[dict[str, Any]]:
    """Return safe provider metadata for operators and UI setup guides."""
    names = {
        "openai": "OpenAI",
        "openai_compat": "OpenAI-compatible gateway",
        "anthropic": "Anthropic",
        "gemini": "Google Gemini",
        "deepseek": "DeepSeek",
        "qwen": "Qwen / DashScope",
        "kimi": "Kimi / Moonshot",
        "glm": "GLM / Zhipu",
        "ollama": "Ollama",
    }
    return [
        {
            "id": provider,
            "name": names.get(provider, provider),
            "protocol": "native" if preset.get("canonical") in {"anthropic", "gemini", "ollama"} else "openai_compatible",
            "default_endpoint": preset.get("base_url"),
            "credential": preset.get("auth", "bearer"),
        }
        for provider, preset in PROVIDER_PRESETS.items()
        if provider not in {"google", "google_gemini", "dashscope", "moonshot", "zhipu"}
    ]


class LLMProviderClient:
    def __init__(self, settings: Any):
        self.settings = settings

    @property
    def provider(self) -> str:
        return str(self.settings.llm_provider).lower().strip()

    def request_spec(self, prompt: str) -> LLMRequestSpec:
        provider = self.provider
        if provider == "disabled":
            raise LLMDisabledError("LLM provider is disabled")

        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai_compat"])
        canonical = preset.get("canonical", provider)
        base_url = self._effective_base_url(preset).rstrip("/")
        self._validate_endpoint(base_url)
        path = self._request_path(canonical)
        url = f"{base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key and preset.get("auth") == "bearer":
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        elif self.settings.llm_api_key and preset.get("auth") == "x-api-key":
            headers["x-api-key"] = self.settings.llm_api_key
            headers["anthropic-version"] = "2023-06-01"
        elif self.settings.llm_api_key and preset.get("auth") == "x-goog-api-key":
            headers["x-goog-api-key"] = self.settings.llm_api_key

        if canonical == "ollama":
            body = {
                "model": self.settings.llm_model_id,
                "messages": self._messages(prompt),
                "stream": False,
            }
        elif canonical == "anthropic":
            body = {
                "model": self.settings.llm_model_id,
                "max_tokens": max(1, int(self.settings.llm_max_output_tokens)),
                "system": "You are an operations analyst for a streaming industrial platform.",
                "messages": [{"role": "user", "content": prompt}],
            }
        elif canonical == "gemini":
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "systemInstruction": {"parts": [{"text": "You are an operations analyst for a streaming industrial platform."}]},
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": max(1, int(self.settings.llm_max_output_tokens))},
            }
        elif self.settings.llm_request_format == "completion":
            body = {
                "model": self.settings.llm_model_id,
                "prompt": prompt,
                "temperature": 0.2,
            }
        else:
            body = {
                "model": self.settings.llm_model_id,
                "messages": self._messages(prompt),
                "temperature": 0.2,
            }

        return LLMRequestSpec(url=url, headers=headers, body=body)

    async def summarize(self, prompt: str, timeout_seconds: int, client: httpx.AsyncClient | None = None) -> str:
        spec = self.request_spec(prompt)
        response_json: dict[str, Any]

        if client is None:
            async with httpx.AsyncClient(timeout=timeout_seconds) as owned_client:
                response_json = await self._post(owned_client, spec)
        else:
            response_json = await self._post(client, spec)
        return self.extract_content(response_json)

    def extract_content(self, response_json: dict[str, Any]) -> str:
        canonical = PROVIDER_PRESETS.get(self.provider, {}).get("canonical", self.provider)
        if canonical == "ollama":
            if "message" in response_json and isinstance(response_json["message"], dict):
                content = response_json["message"].get("content")
                if content is not None:
                    return str(content)
            if "response" in response_json:
                return str(response_json["response"])

        if canonical == "anthropic":
            blocks = response_json.get("content")
            if isinstance(blocks, list):
                text = "".join(str(block.get("text", "")) for block in blocks if isinstance(block, dict))
                if text:
                    return text

        if canonical == "gemini":
            candidates = response_json.get("candidates")
            if isinstance(candidates, list) and candidates:
                parts = ((candidates[0] or {}).get("content") or {}).get("parts", [])
                if isinstance(parts, list):
                    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
                    if text:
                        return text

        choices = response_json.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] or {}
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and message.get("content") is not None:
                    return str(message["content"])
                if first.get("text") is not None:
                    return str(first["text"])

        if response_json.get("content") is not None:
            return str(response_json["content"])

        return json.dumps(response_json, separators=(",", ":"))

    def _request_path(self, canonical: str | None = None) -> str:
        if self.settings.llm_request_path:
            return self._normalize_path(self.settings.llm_request_path)
        canonical = canonical or PROVIDER_PRESETS.get(self.provider, {}).get("canonical", self.provider)
        if canonical == "ollama":
            return "/api/chat"
        if canonical == "anthropic":
            return "/v1/messages"
        if canonical == "gemini":
            model = quote(str(self.settings.llm_model_id).removeprefix("models/"), safe="._-~")
            return f"/v1beta/models/{model}:generateContent"
        return "/chat/completions"

    def _effective_base_url(self, preset: dict[str, str]) -> str:
        configured = str(self.settings.llm_endpoint_url or "").strip()
        default_local = {"", "http://172.17.0.1:1234/v1", "http://host.docker.internal:1234/v1"}
        named_default = preset.get("base_url")
        if named_default and configured in default_local:
            return named_default
        return configured or named_default or "http://localhost:1234/v1"

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path if path.startswith("/") else f"/{path}"

    def _validate_endpoint(self, base_url: str) -> None:
        if not bool(self.settings.llm_local_only):
            return
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        if host in {"localhost", "127.0.0.1", "host.docker.internal"}:
            return
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            raise LLMProviderError(f"Remote LLM endpoint blocked by LLM_LOCAL_ONLY: {base_url}")
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            raise LLMProviderError(f"Remote LLM endpoint blocked by LLM_LOCAL_ONLY: {base_url}")

    @staticmethod
    def _messages(prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": "You are an operations analyst for a streaming industrial platform."},
            {"role": "user", "content": prompt},
        ]

    async def _post(self, client: httpx.AsyncClient, spec: LLMRequestSpec) -> dict[str, Any]:
        response = await client.post(spec.url, headers=spec.headers, json=spec.body)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise LLMProviderError("LLM response must be a JSON object")
        return payload


def build_industrial_prompt(batch: list[dict[str, Any]]) -> str:
    return render_industrial_prompt(batch)


def build_fallback_summary(batch: list[dict[str, Any]], error: str) -> str:
    critical = [event for event in batch if event.get("severity") == "critical"]
    warning = [event for event in batch if event.get("severity") == "warning"]
    devices = sorted({event.get("device_id", "unknown") for event in critical + warning})
    return json.dumps(
        {
            "mode": "deterministic_fallback",
            "status": "ok",
            "reason": error,
            "batch_size": len(batch),
            "critical_count": len(critical),
            "warning_count": len(warning),
            "critical_devices": devices[:10],
            "warning_devices": [event.get("device_id", "unknown") for event in warning][:10],
            "probable_causes": [
                "threshold breach",
                "sensor drift",
                "process instability",
            ],
            "recommended_actions": [
                "Inspect critical devices first",
                "Verify temperature, vibration, and pressure thresholds",
            ],
            "severity_counts": {
                "critical": len(critical),
                "warning": len(warning),
                "normal": max(len(batch) - len(critical) - len(warning), 0),
            },
            "summary": "Deterministic fallback summary generated because the model output was not usable.",
        },
        separators=(",", ":"),
    )
