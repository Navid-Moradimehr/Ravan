from __future__ import annotations

from services.common.agent_runtime import build_agent_runtime_contract
from services.common.agent_tools import tool_registry
from services.common.assistant_store import AssistantStore


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
