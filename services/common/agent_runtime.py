from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.common.modeling import ModelRegistry
from services.common.prompt_registry import prompt_registry


READ_ONLY_PREFIXES = ("historian.", "assets.", "reports.", "scenarios.", "semantic.")
READ_ONLY_TOOL_NAMES = (
    "historian.recent_events",
    "historian.trend",
    "historian.alarms",
    "assets.hierarchy",
    "reports.templates",
    "scenarios.list",
    "semantic.graph_search",
    "semantic.lineage",
)


def _tool_specs() -> list[dict[str, Any]]:
    try:
        from services.common.agent_tools import tool_registry

        return tool_registry.list_tools()
    except Exception:
        return [
            {
                "name": name,
                "description": "read-only diagnostic scaffold",
                "read_only": True,
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object"},
                "tags": ("read_only",),
            }
            for name in READ_ONLY_TOOL_NAMES
        ]


def insert_audit_log(event: dict[str, Any]) -> None:
    try:
        from services.historian.client import insert_audit_log

        insert_audit_log(event)
    except Exception:
        pass


@dataclass(frozen=True)
class AgentPolicy:
    policy_id: str
    role: str
    read_only: bool
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    approval_required: bool = False
    audit_enabled: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentToolCall:
    call_id: str
    tool_name: str
    actor_id: str
    site_id: str = ""
    approved: bool = False
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    occurred_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentRuntimeContract:
    generated_at: str
    model_roles: dict[str, Any]
    prompts: list[dict[str, Any]]
    read_only_tools: list[dict[str, Any]]
    diagnostic_policy: AgentPolicy
    action_policy: AgentPolicy

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "model_roles": self.model_roles,
            "prompts": self.prompts,
            "read_only_tools": self.read_only_tools,
            "diagnostic_policy": self.diagnostic_policy.to_dict(),
            "action_policy": self.action_policy.to_dict(),
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_only_tool_names() -> tuple[str, ...]:
    names = []
    for tool in _tool_specs():
        if tool.get("read_only") and any(str(tool.get("name", "")).startswith(prefix) for prefix in READ_ONLY_PREFIXES):
            names.append(str(tool["name"]))
    if names:
        return tuple(sorted(names))
    return tuple(READ_ONLY_TOOL_NAMES)


def build_agent_runtime_contract() -> dict[str, Any]:
    read_only_tools = [tool for tool in _tool_specs() if tool.get("read_only")]
    diagnostic_policy = AgentPolicy(
        policy_id="diagnostic-readonly",
        role="diagnostic_agent_readonly",
        read_only=True,
        allowed_tools=_read_only_tool_names(),
        approval_required=False,
        audit_enabled=True,
        notes="read-only diagnostic integrations only",
    )
    action_policy = AgentPolicy(
        policy_id="supervised-action",
        role="supervised_action_agent",
        read_only=False,
        allowed_tools=tuple(),
        approval_required=True,
        audit_enabled=True,
        notes="deferred until supervised action governance is available",
    )
    contract = AgentRuntimeContract(
        generated_at=_utc_now(),
        model_roles=ModelRegistry.from_env().export(),
        prompts=prompt_registry.list_templates(),
        read_only_tools=read_only_tools,
        diagnostic_policy=diagnostic_policy,
        action_policy=action_policy,
    )
    return contract.to_dict()


class DiagnosticAgentRuntime:
    """Infrastructure for future read-only diagnostic agents.

    The runtime validates tool usage, records audit events, and keeps action
    execution out of scope. It is intentionally not a shipping agent product.
    """

    def __init__(self, actor_id: str, site_id: str = "", approval_required: bool = False):
        self.actor_id = actor_id
        self.site_id = site_id
        self.approval_required = approval_required

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return _read_only_tool_names()

    def validate_tool_name(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise ValueError(f"tool not allowed for diagnostic runtime: {tool_name}")

    def record_tool_call(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result_summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentToolCall:
        self.validate_tool_name(tool_name)
        record = AgentToolCall(
            call_id=call_id,
            tool_name=tool_name,
            actor_id=self.actor_id,
            site_id=self.site_id,
            approved=not self.approval_required,
            arguments=arguments or {},
            result_summary=result_summary,
            occurred_at=_utc_now(),
            metadata=metadata or {},
        )
        try:
            insert_audit_log(
                {
                    "time": record.occurred_at,
                    "user_id": record.actor_id,
                    "action": "agent_tool_call",
                    "resource": record.tool_name,
                    "details": {
                        "call_id": record.call_id,
                        "site_id": record.site_id,
                        "approved": record.approved,
                        "arguments": record.arguments,
                        "result_summary": record.result_summary,
                        "metadata": record.metadata,
                    },
                }
            )
        except Exception:
            pass
        return record


class SupervisedActionRuntime:
    """Placeholder governance boundary for future action agents."""

    def __init__(self, actor_id: str, site_id: str = ""):
        self.actor_id = actor_id
        self.site_id = site_id

    def request_action(
        self,
        *,
        action_id: str,
        action_name: str,
        target_resource: str,
        requested_by: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "action_id": action_id,
            "action_name": action_name,
            "target_resource": target_resource,
            "requested_by": requested_by,
            "site_id": self.site_id,
            "status": "pending_approval",
            "details": details or {},
            "created_at": _utc_now(),
        }
        try:
            insert_audit_log(
                {
                    "time": payload["created_at"],
                    "user_id": self.actor_id,
                    "action": "agent_action_requested",
                    "resource": target_resource,
                    "details": payload,
                }
            )
        except Exception:
            pass
        return payload
