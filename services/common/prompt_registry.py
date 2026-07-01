from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from string import Template
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
    def __init__(self, templates: list[PromptTemplate] | None = None):
        self._templates: dict[str, PromptTemplate] = {}
        if templates is None:
            self._register_defaults()
        else:
            for template in templates:
                self.register(template)

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

    def get(self, template_id: str) -> PromptTemplate | None:
        return self._templates.get(template_id)

    def list_templates(self) -> list[dict[str, Any]]:
        return [template.to_dict() for template in self._templates.values()]

    def render(self, template_id: str, **variables: Any) -> str:
        template = self.get(template_id)
        if template is None:
            raise KeyError(f"Unknown prompt template: {template_id}")
        return Template(template.template).substitute(**variables)


prompt_registry = PromptRegistry()


def build_industrial_prompt(batch: list[dict[str, Any]]) -> str:
    return prompt_registry.render(
        "industrial-summary-v1",
        batch_json=json.dumps(batch, separators=(",", ":")),
    )

