from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from string import Template
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    version: str
    role: str
    template: str
    output_schema: dict[str, Any]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PromptRegistry:
    def __init__(
        self,
        templates: list[PromptTemplate] | None = None,
        state_path: str | os.PathLike[str] | None = None,
    ):
        self._templates: dict[str, PromptTemplate] = {}
        self._state_path = Path(state_path) if state_path else None
        if self._state_path and self._state_path.exists():
            self._load_state()
        elif templates is None:
            self._register_defaults()
            self._persist_state()
        else:
            for template in templates:
                self.register(template)
            self._persist_state()

    def _register_defaults(self) -> None:
        self.register(
            PromptTemplate(
                template_id="industrial-summary-v1",
                version="1.0.0",
                role="summarization",
                template=(
                    "You are an operations analyst for an industrial streaming platform.\n"
                    "Summarize the processed batch below as valid JSON.\n"
                    "Return keys: summary, critical_devices, warning_devices, probable_causes, "
                    "recommended_actions, batch_size, severity_counts.\n"
                    "Keep the response concise and factual.\n\n"
                    "$batch_json"
                ),
                output_schema={
                    "type": "object",
                    "required": [
                        "summary",
                        "critical_devices",
                        "warning_devices",
                        "probable_causes",
                        "recommended_actions",
                        "batch_size",
                        "severity_counts",
                    ],
                },
                notes="primary summarization prompt for the AI gateway",
            )
        )
        self.register(
            PromptTemplate(
                template_id="diagnostic-readonly-v1",
                version="1.0.0",
                role="diagnostic_agent_readonly",
                template=(
                    "You are a read-only industrial diagnostic assistant.\n"
                    "Use only the provided context and never propose direct actions.\n"
                    "Return concise JSON with findings, evidence, and next_read_only_checks.\n\n"
                    "$context_json"
                ),
                output_schema={
                    "type": "object",
                    "required": ["findings", "evidence", "next_read_only_checks"],
                },
                notes="reserved for future user-integrated diagnostic agents",
            )
        )

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.template_id] = template
        self._persist_state()

    def get(self, template_id: str) -> PromptTemplate | None:
        return self._templates.get(template_id)

    def list_templates(self) -> list[dict[str, Any]]:
        return [template.to_dict() for template in self._templates.values()]

    def render(self, template_id: str, **variables: Any) -> str:
        template = self.get(template_id)
        if template is None:
            raise KeyError(f"Unknown prompt template: {template_id}")
        return Template(template.template).substitute(**variables)

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive bootstrap path
            raise ValueError(f"failed to load prompt registry state from {self._state_path}") from exc

        self._templates = {}
        for item in payload.get("templates", []):
            template = PromptTemplate(
                template_id=item["template_id"],
                version=item["version"],
                role=item["role"],
                template=item["template"],
                output_schema=dict(item.get("output_schema", {})),
                notes=item.get("notes", ""),
            )
            self._templates[template.template_id] = template

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        payload = {"templates": [template.to_dict() for template in self._templates.values()]}
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._state_path)

PROMPT_REGISTRY_PATH = os.environ.get("PROMPT_REGISTRY_PATH")

prompt_registry = PromptRegistry(state_path=PROMPT_REGISTRY_PATH)


def build_industrial_prompt(batch: list[dict[str, Any]]) -> str:
    return prompt_registry.render(
        "industrial-summary-v1",
        batch_json=json.dumps(batch, separators=(",", ":")),
    )
