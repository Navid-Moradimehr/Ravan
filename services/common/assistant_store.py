"""Durable, deployment-light storage for the Ravan assistant.

The default is a small atomic JSON store so Docker Compose and offline installs
do not need another service. The record shapes are deliberately storage-neutral
and can be migrated to the control-plane PostgreSQL database later.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AssistantStore:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path or os.getenv("RAVAN_ASSISTANT_STORE_PATH", ".datastream/assistant-store.json"))
        self._state: dict[str, Any] = {"threads": {}, "memories": [], "action_intents": []}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._state.update(payload)
        except (OSError, ValueError):
            # A corrupt optional assistant store must not prevent the platform
            # API from starting. The next write replaces it atomically.
            self._state = {"threads": {}, "memories": [], "action_intents": []}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix="assistant-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                json.dump(self._state, output, indent=2, sort_keys=True)
            Path(temporary_name).replace(self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def list_threads(self, *, actor_id: str = "local-operator") -> list[dict[str, Any]]:
        return sorted(
            [item for item in self._state["threads"].values() if item.get("actor_id") == actor_id and not item.get("archived")],
            key=lambda item: item.get("updated_at", ""),
            reverse=True,
        )

    def create_thread(self, *, actor_id: str, title: str = "New conversation") -> dict[str, Any]:
        thread_id = f"thread-{uuid.uuid4().hex[:16]}"
        record = {
            "thread_id": thread_id,
            "actor_id": actor_id,
            "title": title[:120] or "New conversation",
            "created_at": _now(),
            "updated_at": _now(),
            "archived": False,
            "messages": [],
        }
        self._state["threads"][thread_id] = record
        self._persist()
        return dict(record)

    def get_thread(self, thread_id: str, *, actor_id: str) -> dict[str, Any] | None:
        record = self._state["threads"].get(thread_id)
        if not record or record.get("actor_id") != actor_id or record.get("archived"):
            return None
        return dict(record)

    def append_message(self, thread_id: str, *, actor_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        record = self.get_thread(thread_id, actor_id=actor_id)
        if record is None:
            raise KeyError(thread_id)
        message = {
            "message_id": f"msg-{uuid.uuid4().hex[:16]}",
            "role": role,
            "content": content,
            "created_at": _now(),
            "metadata": metadata or {},
        }
        self._state["threads"][thread_id]["messages"].append(message)
        self._state["threads"][thread_id]["updated_at"] = message["created_at"]
        self._persist()
        return message

    def archive_thread(self, thread_id: str, *, actor_id: str) -> bool:
        if self.get_thread(thread_id, actor_id=actor_id) is None:
            return False
        self._state["threads"][thread_id]["archived"] = True
        self._state["threads"][thread_id]["updated_at"] = _now()
        self._persist()
        return True

    def add_memory_candidate(self, *, actor_id: str, content: str, source_thread_id: str, scope: str = "user") -> dict[str, Any]:
        candidate = {
            "candidate_id": f"memory-{uuid.uuid4().hex[:16]}",
            "actor_id": actor_id,
            "scope": scope,
            "content": content[:1000],
            "source_thread_id": source_thread_id,
            "status": "pending",
            "created_at": _now(),
        }
        self._state["memories"].append(candidate)
        self._persist()
        return dict(candidate)

    def list_memory_candidates(self, *, actor_id: str) -> list[dict[str, Any]]:
        return [item for item in self._state["memories"] if item.get("actor_id") == actor_id]

    def save_action_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {**payload, "intent_id": payload.get("intent_id") or f"intent-{uuid.uuid4().hex[:16]}", "created_at": payload.get("created_at") or _now(), "status": "pending_confirmation"}
        self._state["action_intents"].append(record)
        self._persist()
        return dict(record)

    def get_action_intent(self, intent_id: str) -> dict[str, Any] | None:
        for item in self._state["action_intents"]:
            if item.get("intent_id") == intent_id:
                return dict(item)
        return None

    def update_action_intent(self, intent_id: str, **updates: Any) -> dict[str, Any] | None:
        for item in self._state["action_intents"]:
            if item.get("intent_id") == intent_id:
                item.update(updates)
                item["updated_at"] = _now()
                self._persist()
                return dict(item)
        return None
