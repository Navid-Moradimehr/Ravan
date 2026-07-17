from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_MODEL_ROLES = (
    "summarization",
    "embeddings",
    "retrieval",
    "diagnostic_agent_readonly",
    "supervised_action_agent",
)


@dataclass(frozen=True)
class ModelBinding:
    role: str
    provider: str
    endpoint_url: str
    model_id: str
    request_format: str = "chat"
    local_only: bool = False
    enabled: bool = True
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    """In-memory model registry for per-site model role selection.

    The registry intentionally stays infrastructure-only. It exposes the model
    roles, capability matrix, and effective configuration surface that future
    diagnostic or action agents can consume later.
    """

    def __init__(
        self,
        bindings: Iterable[ModelBinding] | None = None,
        state_path: str | os.PathLike[str] | None = None,
    ):
        self._bindings: dict[str, ModelBinding] = {}
        self._state_path = Path(state_path) if state_path else None
        if self._state_path and self._state_path.exists():
            self._load_state()
        elif bindings is None:
            self._register_defaults()
            self._persist_state()
        else:
            for binding in bindings:
                self.register(binding)
            self._persist_state()

    @classmethod
    def from_env(cls, state_path: str | os.PathLike[str] | None = None) -> "ModelRegistry":
        if state_path is None:
            state_path = os.getenv("MODEL_REGISTRY_PATH")
        return cls(state_path=state_path)

    @classmethod
    def from_site_profile(cls, profile: Any) -> "ModelRegistry":
        registry = cls()
        runtime_ai = getattr(getattr(profile, "runtime", None), "ai", None)
        if runtime_ai is not None:
            registry.register(
                ModelBinding(
                    role="summarization",
                    provider=str(getattr(runtime_ai, "provider", "disabled")),
                    endpoint_url=str(getattr(runtime_ai, "endpoint_url", "")),
                    model_id=str(getattr(runtime_ai, "model_id", "")),
                    request_format="chat",
                    local_only=bool(getattr(runtime_ai, "local_only", False)),
                    enabled=str(getattr(runtime_ai, "provider", "disabled")).lower() != "disabled",
                    capabilities=("llm", "summarization", "analysis"),
                )
            )
        return registry

    def _register_defaults(self) -> None:
        self._register_role_defaults()
        self.register(
            ModelBinding(
                role="summarization",
                provider="openai_compat",
                endpoint_url=self._env("LLM_ENDPOINT_URL", "http://172.17.0.1:1234/v1"),
                model_id=self._env("LLM_MODEL_ID", "openai/gpt-oss-20b"),
                request_format=self._env("LLM_REQUEST_FORMAT", "chat"),
                local_only=self._env_bool("LLM_LOCAL_ONLY", False),
                enabled=self._env("LLM_PROVIDER", "openai_compat").lower() != "disabled",
                capabilities=("llm", "summarization", "analysis"),
                notes="primary operator-summary model",
            )
        )
        self.register(
            ModelBinding(
                role="embeddings",
                provider=self._env("EMBEDDING_PROVIDER", "openai_compat"),
                endpoint_url=self._env("EMBEDDING_ENDPOINT_URL", "http://172.17.0.1:1234/v1"),
                model_id=self._env("EMBEDDING_MODEL_ID", "text-embedding-nomic-embed-text-v1.5"),
                request_format=self._env("EMBEDDING_REQUEST_FORMAT", "embeddings"),
                local_only=self._env_bool("EMBEDDING_LOCAL_ONLY", False),
                enabled=self._env("EMBEDDING_PROVIDER", "openai_compat").lower() != "disabled",
                capabilities=("embeddings", "retrieval"),
                notes="configure for semantic search and indexing",
            )
        )

    def _register_role_defaults(self) -> None:
        self.register(
            ModelBinding(
                role="retrieval",
                provider="builtin",
                endpoint_url="",
                model_id="",
                request_format="none",
                local_only=True,
                enabled=True,
                capabilities=("historian", "alarms", "assets", "reports"),
                notes="deterministic context assembly boundary",
            )
        )
        self.register(
            ModelBinding(
                role="diagnostic_agent_readonly",
                provider="disabled",
                endpoint_url="",
                model_id="",
                request_format="chat",
                local_only=True,
                enabled=False,
                capabilities=("read_only_tools", "historian", "assets", "reports"),
                notes="reserved for user-integrated diagnostic agents",
            )
        )
        self.register(
            ModelBinding(
                role="supervised_action_agent",
                provider="disabled",
                endpoint_url="",
                model_id="",
                request_format="chat",
                local_only=True,
                enabled=False,
                capabilities=("workflow_hooks", "external_integrations"),
                notes="deferred until supervised action governance is available",
            )
        )

    @staticmethod
    def _env(name: str, default: str) -> str:
        import os

        return os.getenv(name, default)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        import os

        value = os.getenv(name)
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def register(self, binding: ModelBinding) -> None:
        self._bindings[binding.role] = binding
        self._persist_state()

    def get(self, role: str) -> ModelBinding | None:
        return self._bindings.get(role)

    def list_bindings(self) -> list[dict[str, Any]]:
        return [binding.to_dict() for binding in self._bindings.values()]

    def list_roles(self) -> list[str]:
        return list(self._bindings.keys())

    def validate(self) -> list[str]:
        errors: list[str] = []
        for role in DEFAULT_MODEL_ROLES:
            binding = self._bindings.get(role)
            if binding is None:
                errors.append(f"missing role: {role}")
                continue
            if not binding.enabled:
                continue
            if binding.provider == "builtin":
                continue
            if not binding.model_id:
                errors.append(f"{role}: model_id is required")
            if role != "retrieval" and not binding.endpoint_url:
                errors.append(f"{role}: endpoint_url is required")
        return errors

    def export(self) -> dict[str, Any]:
        return {
            "roles": self.list_bindings(),
            "validation_errors": self.validate(),
        }

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive bootstrap path
            raise ValueError(f"failed to load model registry state from {self._state_path}") from exc

        self._bindings = {}
        for item in payload.get("bindings", []):
            binding = ModelBinding(
                role=item["role"],
                provider=item.get("provider", ""),
                endpoint_url=item.get("endpoint_url", ""),
                model_id=item.get("model_id", ""),
                request_format=item.get("request_format", "chat"),
                local_only=bool(item.get("local_only", False)),
                enabled=bool(item.get("enabled", True)),
                capabilities=tuple(item.get("capabilities", ())),
                notes=item.get("notes", ""),
            )
            self._bindings[binding.role] = binding

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        payload = {"bindings": [binding.to_dict() for binding in self._bindings.values()]}
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._state_path)
