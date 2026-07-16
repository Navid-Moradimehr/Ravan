from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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
    from services.historian.client import insert_audit_log as persist_audit_log

    persist_audit_log(event)


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
        return record

    def dispatch_tool(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout_seconds: float = 10.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute one validated read-only tool and return an auditable result."""

        self.validate_tool_name(tool_name)
        if self.approval_required:
            record = self.record_tool_call(call_id=call_id, tool_name=tool_name, arguments=arguments, metadata=metadata, result_summary="approval required")
            return {"call": record.to_dict(), "status": "pending_approval", "result": None}
        try:
            from services.common.agent_tools import execute_read_only_tool

            result = execute_read_only_tool(tool_name, arguments or {}, timeout_seconds=timeout_seconds)
            summary = f"returned {len(result)} records" if isinstance(result, list) else "returned object"
            record = self.record_tool_call(call_id=call_id, tool_name=tool_name, arguments=arguments, result_summary=summary, metadata=metadata)
            return {"call": record.to_dict(), "status": "succeeded", "result": result}
        except Exception as exc:
            record = self.record_tool_call(call_id=call_id, tool_name=tool_name, arguments=arguments, result_summary=f"error: {exc}", metadata={**(metadata or {}), "error_type": type(exc).__name__})
            return {"call": record.to_dict(), "status": "failed", "error": str(exc)}


class ActionRequestLedger:
    """Durable request state; approval never executes an industrial action."""

    def __init__(self, state_path: str | os.PathLike[str] | None = None):
        self._state_path = Path(state_path) if state_path else None
        self._requests: dict[str, dict[str, Any]] = {}
        self._load()

    @classmethod
    def from_env(cls) -> "ActionRequestLedger":
        return cls(os.getenv("AGENT_ACTION_LEDGER_PATH"))

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        action_id = str(payload.get("action_id", "")).strip()
        if not action_id:
            raise ValueError("action_id is required")
        if action_id in self._requests:
            raise ValueError(f"action request already exists: {action_id}")
        record = {**payload, "status": "pending_approval", "created_at": payload.get("created_at") or _utc_now(), "updated_at": _utc_now()}
        self._requests[action_id] = record
        self._persist()
        return dict(record)

    def set_status(self, action_id: str, status: str, *, actor: str, reason: str = "") -> dict[str, Any]:
        if status not in {"approved", "rejected", "cancelled"}:
            raise ValueError(f"unsupported action request status: {status}")
        record = self._requests.get(action_id)
        if record is None:
            raise ValueError(f"unknown action request: {action_id}")
        if record["status"] != "pending_approval":
            raise ValueError(f"action request is already {record['status']}: {action_id}")
        record["status"] = status
        record["updated_at"] = _utc_now()
        record["decision_actor"] = actor
        record["decision_reason"] = reason
        self._persist()
        return dict(record)

    def get(self, action_id: str) -> dict[str, Any] | None:
        record = self._requests.get(action_id)
        return dict(record) if record else None

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        records = self._requests.values()
        if status:
            records = [item for item in records if item["status"] == status]
        return [dict(item) for item in records]

    def _load(self) -> None:
        if not self._state_path or not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._requests = {str(item["action_id"]): item for item in payload.get("requests", [])}

    def _persist(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"requests": list(self._requests.values())}, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)


class SupervisedActionRuntime:
    """Approval-gated request infrastructure with no action execution."""

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
        persisted = ActionRequestLedger.from_env().create(payload)
        insert_audit_log(
            {
                "time": persisted["created_at"],
                "user_id": self.actor_id,
                "action": "agent_action_requested",
                "resource": target_resource,
                "details": persisted,
            }
        )
        return persisted

    def decide(self, action_id: str, *, status: str, actor: str, reason: str = "") -> dict[str, Any]:
        record = ActionRequestLedger.from_env().set_status(action_id, status, actor=actor, reason=reason)
        insert_audit_log(
            {
                "time": record["updated_at"],
                "user_id": actor,
                "action": f"agent_action_{status}",
                "resource": record["target_resource"],
                "details": record,
            }
        )
        return record
