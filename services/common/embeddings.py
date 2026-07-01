from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import ipaddress
import math
import os
import re
from urllib.parse import urlparse
from typing import Any, Iterable

import httpx


_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = "disabled"
    endpoint_url: str = ""
    api_key: str = ""
    model_id: str = "text-embedding-nomic-embed-text-v1.5"
    request_path: str | None = None
    request_format: str = "embeddings"
    timeout_seconds: float = 10.0
    local_only: bool = False
    dimensions: int = 256

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            provider=os.getenv("EMBEDDING_PROVIDER", "openai_compat"),
            endpoint_url=os.getenv("EMBEDDING_ENDPOINT_URL", "http://172.17.0.1:1234/v1"),
            api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", "lm-studio")),
            model_id=os.getenv("EMBEDDING_MODEL_ID", "text-embedding-nomic-embed-text-v1.5"),
            request_path=os.getenv("EMBEDDING_REQUEST_PATH") or None,
            request_format=os.getenv("EMBEDDING_REQUEST_FORMAT", "embeddings"),
            timeout_seconds=float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "10")),
            local_only=str(os.getenv("EMBEDDING_LOCAL_ONLY", "0")).strip().lower() in {"1", "true", "yes", "on"},
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "256")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingBackendInfo:
    provider: str
    endpoint_url: str
    model_id: str
    dimensions: int
    mode: str
    local_only: bool
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EmbeddingError(RuntimeError):
    pass


class EmbeddingDisabledError(EmbeddingError):
    pass


class EmbeddingClient:
    """Provider-neutral embedding client with deterministic fallback.

    The client can talk to OpenAI-compatible services, LM Studio, vLLM, Ollama,
    or any custom HTTP endpoint that exposes an embedding route. If the remote
    backend is unavailable, a stable deterministic embedding is used so tests
    and offline deployments still work.
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        self.config = config or EmbeddingConfig.from_env()

    @property
    def provider(self) -> str:
        return str(self.config.provider).lower().strip()

    @property
    def signature(self) -> str:
        return "|".join(
            [
                self.provider,
                self.config.endpoint_url.rstrip("/"),
                self.config.model_id,
                self.config.request_path or "",
                self.config.request_format,
                str(self.config.dimensions),
            ]
        )

    def backend_info(self) -> EmbeddingBackendInfo:
        notes: list[str] = []
        if self.provider in {"disabled", ""}:
            mode = "deterministic"
            notes.append("remote backend disabled")
        else:
            mode = "remote"
            if self.provider in {"openai_compat", "lmstudio", "vllm"}:
                notes.append("OpenAI-compatible embeddings route")
            elif self.provider == "ollama":
                notes.append("Ollama embeddings route")
            else:
                notes.append("custom HTTP embeddings route")
        return EmbeddingBackendInfo(
            provider=self.provider or "disabled",
            endpoint_url=self.config.endpoint_url,
            model_id=self.config.model_id,
            dimensions=self.config.dimensions,
            mode=mode,
            local_only=self.config.local_only,
            notes=tuple(notes),
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        payload = [str(text) for text in texts]
        if self.provider == "disabled" or not self.config.endpoint_url:
            return [self._fallback_embedding(text) for text in payload]

        try:
            response_json = self._remote_embed(payload)
            vectors = self._extract_embeddings(response_json)
            if len(vectors) == len(payload):
                return vectors
        except Exception:
            pass

        return [self._fallback_embedding(text) for text in payload]

    def _remote_embed(self, texts: list[str]) -> dict[str, Any]:
        base_url = self.config.endpoint_url.rstrip("/")
        self._validate_endpoint(base_url)
        request_path = self._request_path()
        url = f"{base_url}{request_path}"

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        body = self._request_body(texts)
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise EmbeddingError("embedding response must be a JSON object")
        return payload

    def _request_body(self, texts: list[str]) -> dict[str, Any]:
        if self.provider == "ollama":
            prompt = texts[0] if len(texts) == 1 else "\n".join(texts)
            body: dict[str, Any] = {"model": self.config.model_id, "prompt": prompt}
            if len(texts) > 1:
                body["input"] = texts
            return body

        if self.config.request_format == "input":
            return {"model": self.config.model_id, "input": texts if len(texts) > 1 else texts[0]}

        return {"model": self.config.model_id, "input": texts if len(texts) > 1 else texts[0]}

    def _request_path(self) -> str:
        if self.config.request_path:
            return self._normalize_path(self.config.request_path)
        if self.provider == "ollama":
            return "/api/embeddings"
        return "/embeddings"

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path if path.startswith("/") else f"/{path}"

    def _validate_endpoint(self, base_url: str) -> None:
        if not self.config.local_only:
            return
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        if host in {"localhost", "127.0.0.1", "host.docker.internal"}:
            return
        try:
            ip = ipaddress.ip_address(host)
        except ValueError as exc:
            raise EmbeddingError(f"remote embedding endpoint blocked by EMBEDDING_LOCAL_ONLY: {base_url}") from exc
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            raise EmbeddingError(f"remote embedding endpoint blocked by EMBEDDING_LOCAL_ONLY: {base_url}")

    def _extract_embeddings(self, payload: dict[str, Any]) -> list[list[float]]:
        if self.provider == "ollama":
            if isinstance(payload.get("embedding"), list):
                return [self._coerce_vector(payload["embedding"])]
            if isinstance(payload.get("embeddings"), list):
                embeddings = payload["embeddings"]
                if embeddings and isinstance(embeddings[0], list):
                    return [self._coerce_vector(item) for item in embeddings]

        data = payload.get("data")
        if isinstance(data, list):
            vectors: list[list[float]] = []
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("embedding"), list):
                    vectors.append(self._coerce_vector(item["embedding"]))
            if vectors:
                return vectors

        if isinstance(payload.get("embedding"), list):
            return [self._coerce_vector(payload["embedding"])]

        if isinstance(payload.get("embeddings"), list) and payload["embeddings"] and isinstance(payload["embeddings"][0], list):
            return [self._coerce_vector(item) for item in payload["embeddings"]]

        raise EmbeddingError("unsupported embedding response shape")

    def _fallback_embedding(self, text: str) -> list[float]:
        tokens = _TOKEN_RE.findall(text.lower())
        dims = max(self.config.dimensions, 32)
        vector = [0.0] * dims
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.blake2b(f"{self.signature}:{token}".encode("utf-8"), digest_size=16).digest()
            bucket = int.from_bytes(digest[:4], "big") % dims
            weight = 1.0 + (int.from_bytes(digest[4:8], "big") % 1000) / 1000.0
            vector[bucket] += weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]

    @staticmethod
    def _coerce_vector(vector: Iterable[Any]) -> list[float]:
        return [float(value) for value in vector]


def build_embedding_client(settings: Any | None = None) -> EmbeddingClient:
    if settings is None:
        return EmbeddingClient()

    config = EmbeddingConfig(
        provider=str(getattr(settings, "embedding_provider", getattr(settings, "llm_provider", "disabled"))),
        endpoint_url=str(getattr(settings, "embedding_endpoint_url", getattr(settings, "llm_endpoint_url", ""))),
        api_key=str(getattr(settings, "embedding_api_key", getattr(settings, "llm_api_key", ""))),
        model_id=str(getattr(settings, "embedding_model_id", getattr(settings, "llm_model_id", "text-embedding-nomic-embed-text-v1.5"))),
        request_path=getattr(settings, "embedding_request_path", None),
        request_format=str(getattr(settings, "embedding_request_format", "embeddings")),
        timeout_seconds=float(getattr(settings, "embedding_timeout_seconds", getattr(settings, "llm_timeout_seconds", 10))),
        local_only=bool(getattr(settings, "embedding_local_only", getattr(settings, "llm_local_only", False))),
        dimensions=int(getattr(settings, "embedding_dimensions", 256)),
    )
    return EmbeddingClient(config)
