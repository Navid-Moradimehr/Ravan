from __future__ import annotations

import asyncio
from types import SimpleNamespace

from services.api_service.routers.assistant import MessageRequest, QuestionAnswerRequest, RetryRequest, ThreadRequest, _report_action_request, _source_action_request, answer_question, create_thread, retry_failed_turn, send_message
from services.common.agent_runtime import build_agent_runtime_contract
from services.common.agent_tools import tool_registry
from services.common.assistant_store import AssistantStore
from services.common.assistant_skills import get_skill, list_skills


def test_assistant_store_persists_threads_and_reviewable_memory(tmp_path):
    path = tmp_path / "assistant.json"
    store = AssistantStore(path)
    thread = store.create_thread(actor_id="operator-1", title="Plant questions")
    message = store.append_message(thread["thread_id"], actor_id="operator-1", role="user", content="Remember that this site uses metric units.")
    candidate = store.add_memory_candidate(actor_id="operator-1", content=message["content"], source_thread_id=thread["thread_id"])

    reloaded = AssistantStore(path)
    restored = reloaded.get_thread(thread["thread_id"], actor_id="operator-1")
    assert restored is not None
    assert restored["messages"][0]["content"].startswith("Remember")
    assert reloaded.list_memory_candidates(actor_id="operator-1")[0]["candidate_id"] == candidate["candidate_id"]
    reviewed = reloaded.update_memory_candidate(candidate["candidate_id"], actor_id="operator-1", status="approved")
    assert reviewed is not None and reviewed["status"] == "approved"


def test_assistant_runtime_exposes_safe_source_and_governance_tools():
    names = {item["name"] for item in tool_registry.list_tools()}
    assert {"sources.list", "governance.snapshot"}.issubset(names)
    contract = build_agent_runtime_contract()
    allowed = set(contract["diagnostic_policy"]["allowed_tools"])
    assert "sources.list" in allowed
    assert contract["action_policy"]["approval_required"] is True


def test_assistant_store_archives_threads(tmp_path):
    store = AssistantStore(tmp_path / "assistant.json")
    thread = store.create_thread(actor_id="operator-1")
    assert store.archive_thread(thread["thread_id"], actor_id="operator-1") is True
    assert store.list_threads(actor_id="operator-1") == []


def test_action_preview_has_expiry(tmp_path):
    store = AssistantStore(tmp_path / "assistant.json")
    intent = store.save_action_intent({"actor_id": "operator-1", "action_name": "source.test", "target_resource": "conn-1", "confirmation_token": "token"})
    assert intent["status"] == "pending_confirmation"
    assert intent["expires_at"]


def test_assistant_store_tracks_turns_and_retryable_failures(tmp_path):
    store = AssistantStore(tmp_path / "assistant.json")
    thread = store.create_thread(actor_id="operator-1")
    turn = store.start_turn(thread["thread_id"], actor_id="operator-1", content="Explain the pipeline")
    failed = store.update_turn(turn["turn_id"], actor_id="operator-1", status="failed", retryable=True, error={"code": "AI_GATEWAY_TIMEOUT"})
    assert failed and failed["status"] == "failed"
    retryable = store.latest_retryable_turn(thread["thread_id"], actor_id="operator-1")
    assert retryable and retryable["turn_id"] == turn["turn_id"]


def test_natural_language_source_action_requires_unique_registry_match(monkeypatch):
    source = SimpleNamespace(connection_id="conn-pump-1", name="Pump 1", site_id="site-a", state="disabled")
    monkeypatch.setattr("services.api_service.routers.assistant.connection_registry.list", lambda **kwargs: [source])
    action, selected = _source_action_request("enable source conn-pump-1")
    assert action == "source.enable"
    assert selected.connection_id == "conn-pump-1"


def test_natural_language_source_action_stops_on_ambiguous_match(monkeypatch):
    sources = [
        SimpleNamespace(connection_id="conn-pump-1", name="Pump", site_id="site-a", state="disabled"),
        SimpleNamespace(connection_id="conn-pump-2", name="Pump", site_id="site-b", state="disabled"),
    ]
    monkeypatch.setattr("services.api_service.routers.assistant.connection_registry.list", lambda **kwargs: sources)
    action, selected = _source_action_request("enable source Pump")
    assert action == "ambiguous"
    assert len(selected) == 2


def test_report_request_resolves_safe_defaults_and_site_scope():
    assert _report_action_request("generate an anomaly report for site plant-7") == {
        "site_id": "plant-7",
        "report_type": "anomaly",
    }
    assert _report_action_request("please create a report") == {
        "site_id": "*",
        "report_type": "scheduled",
    }


def test_approved_memory_search_excludes_pending_candidates(tmp_path):
    store = AssistantStore(tmp_path / "assistant.json")
    store.add_memory_candidate(actor_id="operator-1", content="Use metric units", source_thread_id="thread-1")
    approved = store.add_memory_candidate(actor_id="operator-1", content="Use imperial units for legacy line", source_thread_id="thread-1")
    store.update_memory_candidate(approved["candidate_id"], actor_id="operator-1", status="approved")
    results = store.search_approved_memories(actor_id="operator-1", query="legacy line")
    assert [item["content"] for item in results] == ["Use imperial units for legacy line"]


def test_declarative_assistant_skills_are_loaded_without_executable_code():
    names = {skill["name"] for skill in list_skills()}
    assert {"ravan-source-onboarding", "ravan-operator-guidance"}.issubset(names)
    source = get_skill("ravan-source-onboarding")
    assert source["approval_required"] is True
    assert "Never send or display secret values" in source["content"]


def test_source_questionnaire_persists_resumes_and_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVAN_ASSISTANT_STORE_PATH", str(tmp_path / "assistant.json"))
    monkeypatch.setattr("services.api_service.routers.assistant.DiagnosticAgentRuntime.dispatch_tool", lambda self, **kwargs: {"status": "succeeded", "result": []})
    thread = asyncio.run(create_thread(ThreadRequest(actor_id="operator-1")))
    first = asyncio.run(send_message(thread["thread_id"], MessageRequest(actor_id="operator-1", content="Connect an OPC UA PLC", context={})))
    questionnaire = first["questionnaire"]
    assert questionnaire["status"] == "pending"
    assert questionnaire["expires_at"]
    invalid = asyncio.run(answer_question(thread["thread_id"], questionnaire["question_id"], QuestionAnswerRequest(actor_id="operator-1", answers={
        "source_protocol": "opcua",
        "name": "Line 1 PLC",
        "site_id": "plant-a",
        "endpoint": "not-an-opcua-endpoint",
    })))
    assert invalid["validation_errors"]
    result = asyncio.run(answer_question(thread["thread_id"], questionnaire["question_id"], QuestionAnswerRequest(actor_id="operator-1", answers={
        "source_protocol": "opcua",
        "name": "Line 1 PLC",
        "site_id": "plant-a",
        "endpoint": "opc.tcp://10.0.0.8:4840",
        "credential_ref": "env://PLC_PASSWORD",
    })))
    assert result["source_draft"]["source_protocol"] == "opcua"
    assert result["questionnaire"]["status"] == "completed"
    try:
        asyncio.run(answer_question(thread["thread_id"], questionnaire["question_id"], QuestionAnswerRequest(actor_id="operator-1", answers={})))
    except Exception as exc:
        assert "not found" in str(exc).lower()


def test_failed_model_turn_can_be_retried(monkeypatch, tmp_path):
    monkeypatch.setenv("RAVAN_ASSISTANT_STORE_PATH", str(tmp_path / "assistant.json"))
    calls = {"count": 0}

    async def model_answer(*args, **kwargs):
        calls["count"] += 1
        return (None, {"code": "AI_GATEWAY_TIMEOUT", "message": "timeout", "phase": "model_call", "retryable": True})

    monkeypatch.setattr("services.api_service.routers.assistant._model_answer", model_answer)
    thread = asyncio.run(create_thread(ThreadRequest(actor_id="operator-1")))
    first = asyncio.run(send_message(thread["thread_id"], MessageRequest(actor_id="operator-1", content="Explain the pipeline", context={"force_gateway": True})))
    assert first["turn"]["status"] == "failed"
    retried = asyncio.run(retry_failed_turn(thread["thread_id"], RetryRequest(actor_id="operator-1")))
    assert retried["turn"]["retry_of"] == first["turn"]["turn_id"]
    assert calls["count"] == 2
