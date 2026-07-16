from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from services.common.agent_runtime import ActionRequestLedger, DiagnosticAgentRuntime, SupervisedActionRuntime, build_agent_runtime_contract
from services.common.agent_tools import build_context_package, tool_registry
from services.common.modeling import ModelRegistry
from services.common.model_lifecycle import ModelLifecycleError, ModelLifecycleLedger
from services.integrations.mlflow_adapter import MLflowAdapter, MLflowAdapterConfig, MLflowAdapterError
from services.common.prompt_registry import prompt_registry


router = APIRouter(tags=["modeling"])


def _lifecycle() -> ModelLifecycleLedger:
    return ModelLifecycleLedger.from_env()


@router.get("/api/v1/modeling/models")
async def list_models() -> dict[str, Any]:
    return {"roles": ModelRegistry.from_env().export(), "versions": _lifecycle().list()}


@router.get("/api/v1/modeling/model-versions")
async def list_model_versions(model_name: str | None = None, site_id: str | None = None) -> list[dict[str, Any]]:
    return _lifecycle().list(model_name=model_name, site_id=site_id)


@router.post("/api/v1/modeling/model-versions")
async def register_model_version(request: dict[str, Any]) -> dict[str, Any]:
    try:
        return _lifecycle().register(
            model_name=str(request.get("model_name", "")),
            version=str(request.get("version", "")),
            provider=str(request.get("provider", "")),
            model_type=str(request.get("model_type", "unknown")),
            artifact_uri=str(request.get("artifact_uri", "")),
            dataset_id=str(request.get("dataset_id", "")),
            manifest_hash=str(request.get("manifest_hash", "")),
            site_id=str(request.get("site_id", "")),
            metadata=dict(request.get("metadata") or {}),
        )
    except (ModelLifecycleError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/modeling/model-versions/{model_id}")
async def get_model_version(model_id: str) -> dict[str, Any]:
    record = _lifecycle().get(model_id)
    if record is None:
        raise HTTPException(status_code=404, detail="model version not found")
    return record


@router.post("/api/v1/modeling/model-versions/{model_id}/evaluations")
async def evaluate_model_version(model_id: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        return _lifecycle().evaluate(
            model_id,
            dataset_id=str(request.get("dataset_id", "")),
            metrics={str(key): float(value) for key, value in dict(request.get("metrics") or {}).items()},
            passed=bool(request.get("passed", False)),
            evaluator=str(request.get("evaluator", "unknown")),
            notes=str(request.get("notes", "")),
        )
    except (ModelLifecycleError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/modeling/model-versions/{model_id}/transitions")
async def transition_model_version(model_id: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        return _lifecycle().transition(model_id, str(request.get("target_state", "")), reason=str(request.get("reason", "")), actor=str(request.get("actor", "operator")))
    except (ModelLifecycleError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/modeling/model-versions/{model_id}/rollback")
async def rollback_model_version(model_id: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        return _lifecycle().rollback(model_id, reason=str(request.get("reason", "rollback")), actor=str(request.get("actor", "operator")))
    except (ModelLifecycleError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/modeling/model-versions/{model_id}/history")
async def model_version_history(model_id: str) -> list[dict[str, Any]]:
    return _lifecycle().history(model_id)


@router.post("/api/v1/modeling/model-versions/{model_id}/sync-mlflow")
async def sync_model_version_to_mlflow(model_id: str) -> dict[str, Any]:
    record = _lifecycle().get(model_id)
    if record is None:
        raise HTTPException(status_code=404, detail="model version not found")
    if not record.get("artifact_uri"):
        raise HTTPException(status_code=400, detail="artifact_uri is required before MLflow synchronization")
    try:
        with MLflowAdapter(MLflowAdapterConfig.from_env()) as adapter:
            result = adapter.register_model(
                record["model_name"],
                record["artifact_uri"],
                tags={"platform_model_id": record["model_id"], "dataset_id": record.get("dataset_id", ""), "manifest_hash": record.get("manifest_hash", "")},
            )
        return {"model_id": model_id, "provider": "mlflow", "result": result}
    except MLflowAdapterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/api/v1/modeling/tools")
async def list_tools() -> list[dict[str, Any]]:
    return tool_registry.list_tools()


@router.get("/api/v1/modeling/prompts")
async def list_prompts() -> list[dict[str, Any]]:
    return prompt_registry.list_templates()


@router.get("/api/v1/modeling/context")
async def get_context(
    asset_id: str | None = None,
    tag: str | None = None,
    table: str = "industrial_events",
    limit: int = 25,
    hours: int = 6,
    site_profile: str | None = None,
) -> dict[str, Any]:
    return build_context_package(
        asset_id=asset_id,
        tag=tag,
        table=table,
        limit=limit,
        hours=hours,
        site_profile_path=Path(site_profile) if site_profile else None,
    )


@router.get("/api/v1/modeling/agent-runtime")
async def get_agent_runtime() -> dict[str, Any]:
    return build_agent_runtime_contract()


@router.post("/api/v1/modeling/diagnostic/dispatch")
async def dispatch_diagnostic_tool(request: dict[str, Any]) -> dict[str, Any]:
    try:
        runtime = DiagnosticAgentRuntime(actor_id=str(request.get("actor_id", "diagnostic-agent")), site_id=str(request.get("site_id", "")), approval_required=bool(request.get("approval_required", False)))
        return runtime.dispatch_tool(
            call_id=str(request.get("call_id", "")) or str(uuid.uuid4()),
            tool_name=str(request.get("tool_name", "")),
            arguments=dict(request.get("arguments") or {}),
            timeout_seconds=float(request.get("timeout_seconds", 10)),
            metadata=dict(request.get("metadata") or {}),
        )
    except (ValueError, TimeoutError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/modeling/agent-actions")
async def list_agent_actions(status: str | None = None) -> list[dict[str, Any]]:
    return ActionRequestLedger.from_env().list(status=status)


@router.post("/api/v1/modeling/agent-actions")
async def request_agent_action(request: dict[str, Any]) -> dict[str, Any]:
    try:
        runtime = SupervisedActionRuntime(actor_id=str(request.get("actor_id", "agent")), site_id=str(request.get("site_id", "")))
        return runtime.request_action(
            action_id=str(request.get("action_id", "")),
            action_name=str(request.get("action_name", "")),
            target_resource=str(request.get("target_resource", "")),
            requested_by=str(request.get("requested_by", request.get("actor_id", "agent"))),
            details=dict(request.get("details") or {}),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/modeling/agent-actions/{action_id}/{decision}")
async def decide_agent_action(action_id: str, decision: str, request: dict[str, Any]) -> dict[str, Any]:
    if decision not in {"approve", "reject", "cancel"}:
        raise HTTPException(status_code=400, detail="decision must be approve, reject, or cancel")
    try:
        status = {"approve": "approved", "reject": "rejected", "cancel": "cancelled"}[decision]
        runtime = SupervisedActionRuntime(actor_id=str(request.get("actor_id", "operator")), site_id=str(request.get("site_id", "")))
        return runtime.decide(action_id, status=status, actor=str(request.get("actor_id", "operator")), reason=str(request.get("reason", "")))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
