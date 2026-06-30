from __future__ import annotations

import json
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any

import httpx


@dataclass(frozen=True)
class LLMRequestSpec:
    url: str
    headers: dict[str, str]
    body: dict[str, Any]


class LLMProviderError(RuntimeError):
    pass


class LLMDisabledError(LLMProviderError):
    pass


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

        base_url = self.settings.llm_endpoint_url.rstrip("/")
        self._validate_endpoint(base_url)
        path = self._request_path()
        url = f"{base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        if provider == "ollama":
            body = {
                "model": self.settings.llm_model_id,
                "messages": self._messages(prompt),
                "stream": False,
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
        if self.provider == "ollama":
            if "message" in response_json and isinstance(response_json["message"], dict):
                content = response_json["message"].get("content")
                if content is not None:
                    return str(content)
            if "response" in response_json:
                return str(response_json["response"])

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

    def _request_path(self) -> str:
        if self.settings.llm_request_path:
            return self._normalize_path(self.settings.llm_request_path)
        if self.provider == "ollama":
            return "/api/chat"
        return "/chat/completions"

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
    return (
        "Summarize this processed industrial IoT batch. Identify critical devices, "
        "probable causes, and operator actions. Return concise JSON.\n\n"
        f"{json.dumps(batch, separators=(',', ':'))}"
    )


def build_fallback_summary(batch: list[dict[str, Any]], error: str) -> str:
    critical = [event for event in batch if event.get("severity") == "critical"]
    warning = [event for event in batch if event.get("severity") == "warning"]
    devices = sorted({event.get("device_id", "unknown") for event in critical + warning})
    return json.dumps(
        {
            "mode": "deterministic_fallback",
            "reason": error,
            "batch_size": len(batch),
            "critical_count": len(critical),
            "warning_count": len(warning),
            "devices": devices[:10],
            "operator_action": "Inspect critical devices first; verify temperature, vibration, and pressure thresholds.",
        },
        separators=(",", ":"),
    )
