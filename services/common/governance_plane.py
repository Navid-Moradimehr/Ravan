from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.common.modeling import ModelRegistry
from services.common.prompt_registry import prompt_registry
from services.common.schema_registry import schema_registry
from services.datasets.runtime_catalog import list_dataset_sources


@dataclass(frozen=True)
class GovernanceIssue:
    area: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_governance_snapshot() -> dict[str, Any]:
    schemas = schema_registry.list_schemas()
    models = ModelRegistry.from_env().export()
    prompts = prompt_registry.list_templates()
    datasets = [dataset.__dict__ for dataset in list_dataset_sources()]

    issues: list[GovernanceIssue] = []
    if models["validation_errors"]:
        for error in models["validation_errors"]:
            issues.append(GovernanceIssue(area="model-registry", severity="warning", message=error))

    if not prompts:
        issues.append(GovernanceIssue(area="prompt-registry", severity="warning", message="no prompt templates registered"))

    if not datasets:
        issues.append(GovernanceIssue(area="dataset-registry", severity="warning", message="no datasets cataloged"))

    schema_compatibility = sorted({schema["compatibility"] for schema in schemas})
    prompt_versions = sorted({prompt["version"] for prompt in prompts})
    model_roles = sorted({binding["role"] for binding in models["roles"]})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "schema_compatibility": schema_compatibility,
        "schema_count": len(schemas),
        "model_roles": model_roles,
        "model_validation_errors": models["validation_errors"],
        "prompt_versions": prompt_versions,
        "prompt_count": len(prompts),
        "dataset_count": len(datasets),
        "issues": [issue.to_dict() for issue in issues],
        "contracts": {
            "schema_governance": True,
            "model_governance": True,
            "prompt_governance": True,
            "promotion_workflow": False,
        },
        "notes": [
            "This is a lifecycle snapshot, not a workflow engine.",
            "Schema compatibility is enforced in application code.",
            "Model and prompt registries stay infrastructure-only until promotion workflows are needed.",
        ],
    }
