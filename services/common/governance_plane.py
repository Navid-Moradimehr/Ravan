from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.common.agent_runtime import build_agent_runtime_contract
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
    agent_contract = build_agent_runtime_contract()

    issues: list[GovernanceIssue] = []
    if models["validation_errors"]:
        for error in models["validation_errors"]:
            issues.append(GovernanceIssue(area="model-registry", severity="warning", message=error))

    if not prompts:
        issues.append(GovernanceIssue(area="prompt-registry", severity="warning", message="no prompt templates registered"))

    if not datasets:
        issues.append(GovernanceIssue(area="dataset-registry", severity="warning", message="no datasets cataloged"))

    if not agent_contract["diagnostic_policy"]["read_only"]:
        issues.append(GovernanceIssue(area="agent-governance", severity="warning", message="diagnostic policy is not read-only"))
    if not agent_contract["action_policy"]["approval_required"]:
        issues.append(GovernanceIssue(area="agent-governance", severity="warning", message="supervised action policy is not approval-gated"))

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
        "agent_governance": agent_contract,
        "issues": [issue.to_dict() for issue in issues],
        "contracts": {
            "schema_governance": True,
            "model_governance": True,
            "prompt_governance": True,
            "agent_governance": True,
            "promotion_workflow": False,
        },
        "notes": [
            "This is a lifecycle snapshot, not a workflow engine.",
            "Schema compatibility is enforced in application code.",
            "Model and prompt registries stay infrastructure-only until promotion workflows are needed.",
            "Diagnostic agents stay read-only.",
            "Supervised action agents stay approval-gated and are not shipped as autonomous executors.",
        ],
    }
