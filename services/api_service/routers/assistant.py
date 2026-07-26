from __future__ import annotations

import os
import re
import secrets
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from services.common.agent_runtime import DiagnosticAgentRuntime, insert_audit_log
from services.common.agent_tools import tool_registry
from services.common.assistant_store import AssistantStore
from services.common.connection_registry import connection_registry
from services.common.connection_diagnostics import run_connection_test
from services.common.ai_reporting import create_report_job, get_policy


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


class ThreadRequest(BaseModel):
    actor_id: str = "local-operator"
    title: str = "New conversation"


class MessageRequest(BaseModel):
    actor_id: str = "local-operator"
    content: str = Field(..., min_length=1, max_length=12000)
    context: dict[str, Any] = Field(default_factory=dict)


class MemoryRequest(BaseModel):
    actor_id: str = "local-operator"
    content: str = Field(..., min_length=1, max_length=1000)


class ActionPreviewRequest(BaseModel):
    actor_id: str = "local-operator"
    action_name: str = Field(..., min_length=1, max_length=100)
    target_resource: str = Field(..., min_length=1, max_length=240)
    details: dict[str, Any] = Field(default_factory=dict)


class ActionConfirmRequest(BaseModel):
    actor_id: str = "local-operator"
    confirmation_token: str = Field(..., min_length=20)


class ActionDecisionRequest(BaseModel):
    actor_id: str = "local-operator"


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000)


def _store() -> AssistantStore:
    return AssistantStore()


def _safe_audit(event: dict[str, Any]) -> None:
    try:
        insert_audit_log(event)
    except Exception:
        # Assistant state changes remain usable when the optional historian
        # audit sink is temporarily unavailable; the failure is not hidden in
        # the action response because the action result still returns.
        return


def _actor(request_actor: str) -> str:
    # Auth remains deployment-owned. This stable local identity is replaced by
    # the authenticated actor adapter when a deployment enables auth.
    return request_actor.strip() or "local-operator"


ALLOWED_ACTIONS = {
    "source.test",
    "source.enable",
    "source.disable",
    "source.retire",
    "source.restore",
    "report.generate",
}


def _deterministic_answer(content: str, context: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    lowered = content.lower()
    route = str(context.get("route") or "the current page")
    if any(term in lowered for term in ("source", "sensor", "plc", "opc ua", "mqtt", "modbus")):
        return (
            "I can help configure a source. Start with the protocol, endpoint, site, credential references, and field mappings. "
            "I can validate and test the draft, then show an activation preview before enabling ingestion. Secrets themselves must stay in the deployment environment.",
            [{"type": "navigate", "href": "/integrations", "label": "Open source connections"}],
        )
    if "kafka" in lowered or "grafana" in lowered or "prometheus" in lowered:
        return (
            "Those operator tools are external to Ravan. I can explain their workflow and take you to the relevant link, but their configuration remains manual and deployment-owned. "
            f"You are currently viewing {route}.",
            [{"type": "navigate", "href": "/", "label": "Open operator links"}],
        )
    if "world model" in lowered or "jepa" in lowered or "dreamer" in lowered or "muzero" in lowered or "xgboost" in lowered:
        return (
            "Ravan records canonical events, lineage, asset relationships, operational context, and versioned datasets. That makes it a data foundation for these models; model training, feature design, and experiment execution remain user-owned.",
            [{"type": "navigate", "href": "/datasets", "label": "Open data readiness"}],
        )
    if "help" in lowered or "guide" in lowered or "how do" in lowered:
        return (
            f"I can guide you through Ravan one step at a time. The current route is {route}. Ask about a panel, source connection, historian query, report, dataset, or external operator tool.",
            [{"type": "navigate", "href": "/help-guidance", "label": "Open help and guidance"}],
        )
    return (
        f"I received your request in {route}. I can inspect Ravan's historian, sources, pipeline, semantic layer, datasets, reports, and model metadata. "
        "For a configuration change I will first collect missing information and show exactly what will change.",
        [],
    )


def _requested_read_tool(content: str) -> tuple[str, dict[str, Any]] | None:
    lowered = content.lower()
    if "source" in lowered or "sensor" in lowered or "plc" in lowered:
        return "sources.list", {}
    if "alarm" in lowered:
        return "historian.alarms", {"limit": 25}
    if "governance" in lowered or "policy boundary" in lowered:
        return "governance.snapshot", {}
    if "recent event" in lowered or "latest event" in lowered:
        return "historian.recent_events", {"table": "industrial_events", "limit": 25}
    return None


def _source_action_request(content: str) -> tuple[str, Any] | None:
    """Resolve only the small, safe source lifecycle vocabulary.

    Natural language never becomes an executable action directly. A unique
    registry match becomes a preview; no match or multiple matches becomes a
    clarification response.
    """
    lowered = content.lower()
    if not any(term in lowered for term in ("source", "sensor", "plc", "connection")):
        return None
    action_match = re.search(r"\b(enable|disable|retire|restore|test)\b", lowered)
    if not action_match:
        return None
    action = f"source.{action_match.group(1)}"
    sources = connection_registry.list(include_retired=True)
    id_match = re.search(r"\b(conn-[a-z0-9_-]+)\b", lowered)
    if id_match:
        selected = [source for source in sources if source.connection_id.lower() == id_match.group(1)]
    else:
        selected = [source for source in sources if source.name.lower() in lowered]
    if len(selected) == 1:
        return action, selected[0]
    if len(selected) > 1:
        return "ambiguous", selected
    return "missing", sources


def _report_action_request(content: str) -> dict[str, Any] | None:
    lowered = content.lower()
    if "report" not in lowered or not re.search(r"\b(generate|create|run|queue)\b", lowered):
        return None
    site_match = re.search(r"\bsite(?:\s+id)?\s*[:=/-]?\s*([a-z0-9_.-]+)", lowered)
    site_id = site_match.group(1) if site_match else "*"
    report_type = "anomaly" if "anomaly" in lowered else "scheduled"
    return {"site_id": site_id, "report_type": report_type}


def _make_action_preview(*, actor_id: str, action_name: str, source: Any) -> dict[str, Any]:
    intent = _store().save_action_intent({
        "actor_id": actor_id,
        "action_name": action_name,
        "target_resource": source.connection_id,
        "details": {
            "connection_id": source.connection_id,
            "source_name": source.name,
            "site_id": source.site_id,
            "current_state": source.state,
        },
        "confirmation_token": secrets.token_urlsafe(24),
        "preview": f"Confirm {action_name.replace('source.', '')} for {source.name} ({source.connection_id})",
    })
    _safe_audit({"time": intent["created_at"], "user_id": actor_id, "action": "assistant_action_previewed", "resource": source.connection_id, "details": intent})
    return intent


async def _model_answer(content: str, context: dict[str, Any]) -> str | None:
    """Use the existing provider-neutral gateway when it is available."""
    base = os.getenv("DATASTREAM_AI_BASE", "http://localhost:8080").rstrip("/")
    memory_context = context.get("approved_memory", [])
    prompt = (
        "You are the Ravan industrial data platform assistant. Answer clearly and briefly. "
        "Never invent current system state, never expose secrets, never issue plant-control commands, and distinguish platform-owned work from user-owned work.\n\n"
        f"Current UI context: {context}\nApproved operator memory (use only when relevant): {memory_context}\nUser request: {content}"
    )
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(f"{base}/assistant/chat", json={"prompt": prompt})
            if response.status_code != 200:
                return None
            payload = response.json()
            answer = payload.get("content")
            return str(answer).strip() if answer else None
    except (httpx.HTTPError, ValueError):
        return None


@router.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {
        "voice": {"enabled": bool(os.getenv("RAVAN_STT_URL")), "tts_enabled": bool(os.getenv("RAVAN_TTS_URL")), "mode": "push_to_talk", "audio_retained": False},
        "external_tools": {"kafka_ui": "guidance_only", "grafana": "guidance_only", "prometheus": "guidance_only"},
        "read_only_tools": tool_registry.list_tools(),
        "action_boundary": "no_plc_or_actuator_control",
        "memory": {"threads": True, "reviewed_candidates": True, "vector_backend": "optional"},
    }


@router.get("/threads")
async def list_threads(actor_id: str = "local-operator") -> list[dict[str, Any]]:
    return _store().list_threads(actor_id=_actor(actor_id))


@router.post("/threads")
async def create_thread(request: ThreadRequest) -> dict[str, Any]:
    return _store().create_thread(actor_id=_actor(request.actor_id), title=request.title)


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str, actor_id: str = "local-operator") -> dict[str, Any]:
    thread = _store().get_thread(thread_id, actor_id=_actor(actor_id))
    if thread is None:
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    return thread


@router.delete("/threads/{thread_id}")
async def archive_thread(thread_id: str, actor_id: str = "local-operator") -> dict[str, Any]:
    if not _store().archive_thread(thread_id, actor_id=_actor(actor_id)):
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    return {"ok": True, "thread_id": thread_id, "status": "archived"}


@router.post("/threads/{thread_id}/messages")
async def send_message(thread_id: str, request: MessageRequest) -> dict[str, Any]:
    actor_id = _actor(request.actor_id)
    store = _store()
    if store.get_thread(thread_id, actor_id=actor_id) is None:
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    user_message = store.append_message(thread_id, actor_id=actor_id, role="user", content=request.content, metadata={"context": request.context})
    action_preview = None
    action_request = _source_action_request(request.content)
    action_clarification = None
    if action_request is not None:
        action_kind, source_match = action_request
        if action_kind == "ambiguous":
            names = ", ".join(f"{source.name} ({source.connection_id})" for source in source_match[:10])
            action_clarification = f"I found multiple matching sources: {names}. Please include the exact connection ID before I prepare a change."
        elif action_kind == "missing":
            action_clarification = "I could not resolve that source from the registry. Include its exact connection ID, or create/save it in Source connections first."
        else:
            action_preview = _make_action_preview(actor_id=actor_id, action_name=action_kind, source=source_match)
    report_request = None if action_preview or action_clarification else _report_action_request(request.content)
    if report_request:
        try:
            policy = get_policy(report_request["site_id"])
            if not policy.enabled:
                action_clarification = f"AI reporting is disabled for site scope {report_request['site_id']}. Enable the policy in AI Reporting before requesting a report."
            else:
                action_preview = store.save_action_intent({
                    "actor_id": actor_id,
                    "action_name": "report.generate",
                    "target_resource": report_request["site_id"],
                    "details": {**report_request, "window_hours": 1},
                    "confirmation_token": secrets.token_urlsafe(24),
                    "preview": f"Confirm {report_request['report_type']} report for site {report_request['site_id']}",
                })
                _safe_audit({"time": action_preview["created_at"], "user_id": actor_id, "action": "assistant_action_previewed", "resource": report_request["site_id"], "details": action_preview})
        except Exception as exc:
            action_clarification = f"I could not prepare the report preview: {exc}"
    tool_result = None
    requested_tool = _requested_read_tool(request.content)
    if requested_tool is not None:
        tool_name, arguments = requested_tool
        runtime = DiagnosticAgentRuntime(actor_id=actor_id, site_id=str(request.context.get("site_id", "")))
        try:
            tool_result = runtime.dispatch_tool(call_id=user_message["message_id"], tool_name=tool_name, arguments=arguments, metadata={"assistant": True})
        except (ValueError, TimeoutError) as exc:
            tool_result = {"status": "failed", "error": str(exc)}
    links: list[dict[str, Any]] = []
    if action_preview:
        if action_preview["action_name"].startswith("source."):
            answer = f"I prepared a reviewable preview for {action_preview['details']['source_name']} at site {action_preview['details']['site_id']}. Nothing has changed yet. Confirm it below to continue."
        else:
            answer = f"I prepared a reviewable preview for {action_preview['preview']}. Nothing has been queued yet. Confirm it below to continue."
    elif action_clarification:
        answer = action_clarification
    else:
        approved_memory = [item["content"] for item in store.list_memory_candidates(actor_id=actor_id) if item.get("status") == "approved"]
        model_context = {**request.context, "approved_memory": approved_memory[-20:]}
        answer = await _model_answer(request.content, model_context)
        if not answer:
            answer, links = _deterministic_answer(request.content, request.context)
    if tool_result and tool_result.get("status") == "succeeded":
        count = len(tool_result.get("result", [])) if isinstance(tool_result.get("result"), list) else 1
        answer = f"I checked {requested_tool[0] if requested_tool else 'the requested data'} and found {count} result(s). The detailed result is available in the assistant context.\n\n{answer}"
    assistant_message = store.append_message(thread_id, actor_id=actor_id, role="assistant", content=answer, metadata={"links": links, "provider": "gateway" if not action_preview and not action_clarification else "deterministic", "tool_result": tool_result, "action_preview": action_preview})
    if request.content.lower().startswith(("remember that", "i prefer", "always ")):
        candidate = store.add_memory_candidate(actor_id=actor_id, content=request.content, source_thread_id=thread_id)
    else:
        candidate = None
    return {"user_message": user_message, "assistant_message": assistant_message, "links": links, "tool_result": tool_result, "memory_candidate": candidate, "action_preview": action_preview}


@router.get("/memory/candidates")
async def list_memory_candidates(actor_id: str = "local-operator") -> list[dict[str, Any]]:
    return _store().list_memory_candidates(actor_id=_actor(actor_id))


@router.get("/memory/search")
async def search_memory(query: str = "", actor_id: str = "local-operator", limit: int = 20) -> list[dict[str, Any]]:
    """Return only operator-approved memory; this is the local fallback for semantic recall."""
    return _store().search_approved_memories(actor_id=_actor(actor_id), query=query, limit=limit)


@router.post("/memory/candidates")
async def create_memory_candidate(request: MemoryRequest, thread_id: str = "manual") -> dict[str, Any]:
    return _store().add_memory_candidate(actor_id=_actor(request.actor_id), content=request.content, source_thread_id=thread_id)


@router.post("/memory/candidates/{candidate_id}/{decision}")
async def decide_memory_candidate(candidate_id: str, decision: str, request: ThreadRequest) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be approve or reject")
    try:
        record = _store().update_memory_candidate(candidate_id, actor_id=_actor(request.actor_id), status="approved" if decision == "approve" else "rejected")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="memory candidate not found")
    _safe_audit({"time": record["reviewed_at"], "user_id": _actor(request.actor_id), "action": f"assistant_memory_{decision}", "resource": candidate_id, "details": record})
    return record


@router.post("/actions/preview")
async def preview_action(request: ActionPreviewRequest) -> dict[str, Any]:
    if request.action_name not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"unsupported assistant action: {request.action_name}")
    if request.action_name.startswith("source.") and not request.details.get("connection_id"):
        raise HTTPException(status_code=422, detail="connection_id is required for source actions")
    token = secrets.token_urlsafe(24)
    intent = _store().save_action_intent({
        "actor_id": _actor(request.actor_id),
        "action_name": request.action_name,
        "target_resource": request.target_resource,
        "details": request.details,
        "confirmation_token": token,
        "preview": f"Confirm {request.action_name} for {request.target_resource}",
    })
    _safe_audit({"time": intent["created_at"], "user_id": intent["actor_id"], "action": "assistant_action_previewed", "resource": intent["target_resource"], "details": intent})
    return intent


@router.post("/actions/{intent_id}/confirm")
async def confirm_action(intent_id: str, request: ActionConfirmRequest) -> dict[str, Any]:
    store = _store()
    intent = store.get_action_intent(intent_id)
    if intent is None or intent.get("actor_id") != _actor(request.actor_id):
        raise HTTPException(status_code=404, detail="assistant action preview not found")
    if intent.get("status") != "pending_confirmation":
        raise HTTPException(status_code=409, detail=f"assistant action is already {intent.get('status')}")
    from datetime import datetime, timezone
    if intent.get("expires_at") and datetime.fromisoformat(str(intent["expires_at"])) <= datetime.now(timezone.utc):
        store.update_action_intent(intent_id, status="expired")
        raise HTTPException(status_code=409, detail="assistant action preview has expired")
    if not secrets.compare_digest(str(intent.get("confirmation_token", "")), request.confirmation_token):
        raise HTTPException(status_code=409, detail="confirmation token does not match this preview")
    details = dict(intent.get("details") or {})
    connection_id = str(details.get("connection_id", ""))
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="source connection not found")
    action = str(intent["action_name"])
    try:
        if action == "source.test":
            result = run_connection_test(connection)
        elif action == "source.enable":
            result = connection_registry.set_enabled(connection_id, True).to_dict()
        elif action == "source.disable":
            result = connection_registry.set_enabled(connection_id, False).to_dict()
        elif action == "source.retire":
            result = connection_registry.retire(connection_id).to_dict()
        elif action == "source.restore":
            result = connection_registry.restore(connection_id).to_dict()
        elif action == "report.generate":
            from datetime import timedelta
            site_id = str(details.get("site_id") or "*")
            policy = get_policy(site_id)
            if not policy.enabled:
                raise ValueError(f"AI reporting is disabled for site scope {site_id}")
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=float(details.get("window_hours", 1)))
            result = create_report_job(site_id=site_id, report_type=str(details.get("report_type", "scheduled")), trigger_reason="assistant_confirmed", window_start=start, window_end=end, policy=policy)
        else:
            raise ValueError(f"unsupported assistant action: {action}")
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    completed = store.update_action_intent(intent_id, status="completed", result=result) or intent
    _safe_audit({"time": completed.get("updated_at"), "user_id": _actor(request.actor_id), "action": "assistant_action_completed", "resource": intent["target_resource"], "details": completed})
    return {"intent": completed, "result": result}


@router.post("/actions/{intent_id}/reject")
async def reject_action(intent_id: str, request: ActionDecisionRequest) -> dict[str, Any]:
    actor_id = _actor(request.actor_id)
    intent = _store().get_action_intent(intent_id)
    if intent is None or intent.get("actor_id") != actor_id:
        raise HTTPException(status_code=404, detail="assistant action preview not found")
    if intent.get("status") != "pending_confirmation":
        raise HTTPException(status_code=409, detail=f"assistant action is already {intent.get('status')}")
    rejected = _store().update_action_intent(intent_id, status="rejected") or intent
    _safe_audit({"time": rejected.get("updated_at"), "user_id": actor_id, "action": "assistant_action_rejected", "resource": intent["target_resource"], "details": rejected})
    return {"intent": rejected, "status": "rejected"}


@router.post("/voice/transcribe")
async def transcribe_voice(request: Request) -> dict[str, Any]:
    stt_url = os.getenv("RAVAN_STT_URL", "").strip()
    if not stt_url:
        raise HTTPException(status_code=503, detail="voice transcription is not configured; set RAVAN_STT_URL")
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=422, detail="audio body is empty")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(stt_url, content=audio, headers={"Content-Type": request.headers.get("content-type", "audio/webm")})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"speech-to-text provider failed: {exc}") from exc
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=502, detail="speech-to-text provider returned no transcript")
    return {"text": text, "audio_retained": False}


@router.post("/voice/synthesize")
async def synthesize_voice(request: VoiceSynthesisRequest) -> dict[str, Any]:
    tts_url = os.getenv("RAVAN_TTS_URL", "").strip()
    if not tts_url:
        raise HTTPException(status_code=503, detail="voice synthesis is not configured; set RAVAN_TTS_URL")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(tts_url, json={"text": request.text})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"text-to-speech provider failed: {exc}") from exc
    return Response(content=response.content, media_type=response.headers.get("content-type", "audio/mpeg"), headers={"X-Ravan-Audio-Retained": "false"})


@router.post("/diagnostic")
async def diagnostic(request: dict[str, Any]) -> dict[str, Any]:
    runtime = DiagnosticAgentRuntime(actor_id=str(request.get("actor_id", "local-operator")), site_id=str(request.get("site_id", "")))
    try:
        return runtime.dispatch_tool(call_id=str(request.get("call_id", "assistant")), tool_name=str(request.get("tool_name", "")), arguments=dict(request.get("arguments") or {}), metadata={"assistant": True})
    except (ValueError, TimeoutError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
