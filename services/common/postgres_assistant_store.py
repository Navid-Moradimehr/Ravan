"""PostgreSQL-backed assistant repository for multi-replica deployments.

This adapter deliberately implements the existing AssistantStore contract. It
does not make PostgreSQL mandatory for local installs and can be selected with
``RAVAN_ASSISTANT_STORE_BACKEND=postgres``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from services.historian.client import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PostgresAssistantStore:
    def __init__(self) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ravan_assistant_records (
                        record_id TEXT PRIMARY KEY,
                        record_type TEXT NOT NULL,
                        actor_id TEXT,
                        thread_id TEXT,
                        status TEXT,
                        payload JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS ravan_assistant_thread_idx ON ravan_assistant_records(record_type, actor_id, updated_at DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS ravan_assistant_turn_idx ON ravan_assistant_records(record_type, thread_id, actor_id, updated_at DESC)")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ravan_assistant_turns (
                        turn_id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        context JSONB NOT NULL DEFAULT '{}'::jsonb,
                        retry_of TEXT,
                        attempt INTEGER NOT NULL DEFAULT 1,
                        status TEXT NOT NULL,
                        retryable BOOLEAN NOT NULL DEFAULT FALSE,
                        error JSONB,
                        response_message_id TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS ravan_assistant_turns_claim_idx ON ravan_assistant_turns(status, heartbeat_at)")
                cur.execute("CREATE INDEX IF NOT EXISTS ravan_assistant_turns_thread_idx ON ravan_assistant_turns(thread_id, actor_id, updated_at DESC)")
            conn.commit()

    def _fetch_one(self, record_type: str, record_id: str, *, actor_id: str | None = None, for_update: bool = False) -> dict[str, Any] | None:
        query = "SELECT payload FROM ravan_assistant_records WHERE record_type=%s AND record_id=%s"
        params: list[Any] = [record_type, record_id]
        if actor_id is not None:
            query += " AND actor_id=%s"
            params.append(actor_id)
        if for_update:
            query += " FOR UPDATE"
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
            if for_update:
                conn.commit()
        return dict(row["payload"]) if row else None

    def _upsert(self, *, record_id: str, record_type: str, payload: dict[str, Any], actor_id: str | None = None, thread_id: str | None = None, status: str | None = None) -> dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ravan_assistant_records(record_id, record_type, actor_id, thread_id, status, payload)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(record_id) DO UPDATE SET actor_id=EXCLUDED.actor_id,
                        thread_id=EXCLUDED.thread_id, status=EXCLUDED.status,
                        payload=EXCLUDED.payload, updated_at=NOW()
                    """,
                    (record_id, record_type, actor_id, thread_id, status, Json(payload)),
                )
            conn.commit()
        return dict(payload)

    def list_threads(self, *, actor_id: str = "local-operator", include_archived: bool = False) -> list[dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT payload FROM ravan_assistant_records WHERE record_type='thread' AND actor_id=%s"
                if not include_archived:
                    query += " AND COALESCE((payload->>'archived')::boolean, false)=false"
                query += " ORDER BY updated_at DESC"
                cur.execute(query, (actor_id,))
                return [dict(row["payload"]) for row in cur.fetchall()]

    def create_thread(self, *, actor_id: str, title: str = "New conversation") -> dict[str, Any]:
        now = _now()
        record = {"thread_id": f"thread-{uuid.uuid4().hex[:16]}", "actor_id": actor_id, "title": title[:120] or "New conversation", "created_at": now, "updated_at": now, "archived": False, "messages": []}
        return self._upsert(record_id=record["thread_id"], record_type="thread", actor_id=actor_id, payload=record)

    def get_thread(self, thread_id: str, *, actor_id: str) -> dict[str, Any] | None:
        record = self._fetch_one("thread", thread_id, actor_id=actor_id)
        return record if record and not record.get("archived") else None

    def append_message(self, thread_id: str, *, actor_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        message = {"message_id": f"msg-{uuid.uuid4().hex[:16]}", "role": role, "content": content, "created_at": _now(), "metadata": metadata or {}}
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT payload FROM ravan_assistant_records WHERE record_type='thread' AND record_id=%s AND actor_id=%s AND COALESCE((payload->>'archived')::boolean, false)=false FOR UPDATE", (thread_id, actor_id))
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    raise KeyError(thread_id)
                record = dict(row["payload"])
                record.setdefault("messages", []).append(message)
                record["updated_at"] = message["created_at"]
                cur.execute("UPDATE ravan_assistant_records SET payload=%s, updated_at=NOW() WHERE record_type='thread' AND record_id=%s", (Json(record), thread_id))
            conn.commit()
        return message

    def start_turn(self, thread_id: str, *, actor_id: str, content: str, context: dict[str, Any] | None = None, retry_of: str | None = None) -> dict[str, Any]:
        if self.get_thread(thread_id, actor_id=actor_id) is None:
            raise KeyError(thread_id)
        now = _now()
        record = {"turn_id": f"turn-{uuid.uuid4().hex[:16]}", "thread_id": thread_id, "actor_id": actor_id, "content": content, "context": context or {}, "retry_of": retry_of, "attempt": 1, "status": "running", "created_at": now, "updated_at": now}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO ravan_assistant_turns(turn_id, thread_id, actor_id, content, context, retry_of, status, created_at, updated_at, heartbeat_at) VALUES (%s,%s,%s,%s,%s,%s,'running',%s,%s,%s)", (record["turn_id"], thread_id, actor_id, content, Json(context or {}), retry_of, now, now, now))
            conn.commit()
        return self._upsert(record_id=record["turn_id"], record_type="turn", actor_id=actor_id, thread_id=thread_id, status="running", payload=record)

    def get_turn(self, turn_id: str, *, actor_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ravan_assistant_turns WHERE turn_id=%s AND actor_id=%s", (turn_id, actor_id))
                row = cur.fetchone()
        if row:
            return self._turn_record(dict(row))
        return self._fetch_one("turn", turn_id, actor_id=actor_id)

    @staticmethod
    def _turn_record(row: dict[str, Any]) -> dict[str, Any]:
        return {"turn_id": row["turn_id"], "thread_id": row["thread_id"], "actor_id": row["actor_id"], "content": row["content"], "context": row.get("context") or {}, "retry_of": row.get("retry_of"), "attempt": row.get("attempt", 1), "status": row["status"], "retryable": row.get("retryable", False), "error": row.get("error"), "response_message_id": row.get("response_message_id"), "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"], "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else row["updated_at"]}

    def update_turn(self, turn_id: str, *, actor_id: str, **updates: Any) -> dict[str, Any] | None:
        record = self._fetch_one("turn", turn_id, actor_id=actor_id)
        if not record:
            return None
        record.update(updates)
        record["updated_at"] = _now()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE ravan_assistant_turns SET status=%s, retryable=%s, error=%s, response_message_id=%s, context=%s, updated_at=NOW(), heartbeat_at=NOW() WHERE turn_id=%s AND actor_id=%s", (record.get("status"), bool(record.get("retryable")), Json(record.get("error")) if record.get("error") is not None else None, record.get("response_message_id"), Json(record.get("context") or {}), turn_id, actor_id))
            conn.commit()
        return self._upsert(record_id=turn_id, record_type="turn", actor_id=actor_id, thread_id=record.get("thread_id"), status=record.get("status"), payload=record)

    def claim_turn(self, turn_id: str, *, actor_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("UPDATE ravan_assistant_turns SET status='executing', heartbeat_at=NOW(), updated_at=NOW() WHERE turn_id=%s AND actor_id=%s AND status='running' RETURNING *", (turn_id, actor_id))
                row = cur.fetchone()
            conn.commit()
        return self._turn_record(dict(row)) if row else None

    def heartbeat_turn(self, turn_id: str, *, actor_id: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE ravan_assistant_turns SET heartbeat_at=NOW(), updated_at=NOW() WHERE turn_id=%s AND actor_id=%s AND status IN ('running','executing')", (turn_id, actor_id))
                changed = cur.rowcount
            conn.commit()
        return bool(changed)

    def latest_retryable_turn(self, thread_id: str, *, actor_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ravan_assistant_turns WHERE thread_id=%s AND actor_id=%s AND status='failed' AND retryable=true ORDER BY updated_at DESC LIMIT 1", (thread_id, actor_id))
                row = cur.fetchone()
        return self._turn_record(dict(row)) if row else None

    def latest_running_turn(self, thread_id: str, *, actor_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ravan_assistant_turns WHERE thread_id=%s AND actor_id=%s AND status IN ('running','executing') ORDER BY updated_at DESC LIMIT 1", (thread_id, actor_id))
                row = cur.fetchone()
        return self._turn_record(dict(row)) if row else None

    def reap_stale_turns(self, *, max_age_seconds: int = 300) -> int:
        """Atomically fail abandoned running turns across replicas."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ravan_assistant_turns
                    SET status='failed', retryable=true, error=%s, updated_at=NOW(), heartbeat_at=NOW()
                    WHERE status IN ('running','executing')
                      AND heartbeat_at < NOW() - (%s * INTERVAL '1 second')
                    """,
                    (Json({"code": "ASSISTANT_TURN_REAPED", "message": "The assistant turn expired before completion."}), max(30, max_age_seconds)),
                )
                changed = cur.rowcount
            conn.commit()
        return int(changed)

    def record_tool_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = {**payload, "tool_call_id": payload.get("tool_call_id") or f"tool-{uuid.uuid4().hex[:16]}", "created_at": payload.get("created_at") or _now(), "status": payload.get("status", "running")}
        return self._upsert(record_id=record["tool_call_id"], record_type="tool_call", actor_id=record.get("actor_id"), thread_id=record.get("thread_id"), status=record.get("status"), payload=record)

    def update_tool_call(self, tool_call_id: str, **updates: Any) -> dict[str, Any] | None:
        record = self._fetch_one("tool_call", tool_call_id)
        if not record:
            return None
        record.update(updates)
        record["updated_at"] = _now()
        return self._upsert(record_id=tool_call_id, record_type="tool_call", actor_id=record.get("actor_id"), thread_id=record.get("thread_id"), status=record.get("status"), payload=record)

    def update_message_metadata(self, thread_id: str, message_id: str, *, actor_id: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT payload FROM ravan_assistant_records WHERE record_type='thread' AND record_id=%s AND actor_id=%s FOR UPDATE", (thread_id, actor_id))
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None
                record = dict(row["payload"])
                for message in record.get("messages", []):
                    if message.get("message_id") == message_id:
                        message["metadata"] = {**dict(message.get("metadata") or {}), **metadata}
                        record["updated_at"] = _now()
                        cur.execute("UPDATE ravan_assistant_records SET payload=%s, updated_at=NOW() WHERE record_type='thread' AND record_id=%s", (Json(record), thread_id))
                        conn.commit()
                        return dict(message)
            conn.rollback()
        return None

    def archive_thread(self, thread_id: str, *, actor_id: str) -> bool:
        record = self.get_thread(thread_id, actor_id=actor_id)
        if not record:
            return False
        record["archived"] = True
        record["updated_at"] = _now()
        self._upsert(record_id=thread_id, record_type="thread", actor_id=actor_id, payload=record)
        return True

    def restore_thread(self, thread_id: str, *, actor_id: str) -> bool:
        record = self._fetch_one("thread", thread_id, actor_id=actor_id)
        if not record:
            return False
        record["archived"] = False
        record["updated_at"] = _now()
        self._upsert(record_id=thread_id, record_type="thread", actor_id=actor_id, payload=record)
        return True

    def delete_thread_permanently(self, thread_id: str, *, actor_id: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM ravan_assistant_records WHERE record_type='thread' AND record_id=%s AND actor_id=%s AND COALESCE((payload->>'archived')::boolean, false)=true",
                    (thread_id, actor_id),
                )
                if cur.fetchone() is None:
                    conn.rollback()
                    return False
                cur.execute("DELETE FROM ravan_assistant_records WHERE record_type='thread' AND record_id=%s AND actor_id=%s", (thread_id, actor_id))
                cur.execute("DELETE FROM ravan_assistant_records WHERE thread_id=%s AND actor_id=%s", (thread_id, actor_id))
            conn.commit()
        return True

    def rename_thread(self, thread_id: str, *, actor_id: str, title: str) -> dict[str, Any] | None:
        record = self._fetch_one("thread", thread_id, actor_id=actor_id)
        if not record or record.get("archived"):
            return None
        record["title"] = title.strip()[:120] or "New conversation"
        record["updated_at"] = _now()
        return self._upsert(record_id=thread_id, record_type="thread", actor_id=actor_id, payload=record)

    def add_memory_candidate(self, *, actor_id: str, content: str, source_thread_id: str, scope: str = "user") -> dict[str, Any]:
        record = {"candidate_id": f"memory-{uuid.uuid4().hex[:16]}", "actor_id": actor_id, "scope": scope, "content": content[:1000], "source_thread_id": source_thread_id, "status": "pending", "created_at": _now()}
        return self._upsert(record_id=record["candidate_id"], record_type="memory", actor_id=actor_id, thread_id=source_thread_id, status="pending", payload=record)

    def update_memory_candidate(self, candidate_id: str, *, actor_id: str, status: str) -> dict[str, Any] | None:
        if status not in {"approved", "rejected"}:
            raise ValueError("memory candidate status must be approved or rejected")
        record = self._fetch_one("memory", candidate_id, actor_id=actor_id)
        if not record:
            return None
        record.update({"status": status, "reviewed_at": _now()})
        return self._upsert(record_id=candidate_id, record_type="memory", actor_id=actor_id, thread_id=record.get("source_thread_id"), status=status, payload=record)

    def list_memory_candidates(self, *, actor_id: str) -> list[dict[str, Any]]:
        return self._list_payloads("memory", actor_id=actor_id)

    def search_approved_memories(self, *, actor_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        tokens = [part.lower() for part in query.split() if len(part.strip()) > 2]
        records = [item for item in self._list_payloads("memory", actor_id=actor_id) if item.get("status") == "approved"]
        ranked = [(sum(1 for token in tokens if token in str(item.get("content", "")).lower()), item.get("created_at", ""), item) for item in records]
        ranked = [item for item in ranked if not tokens or item[0]]
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in ranked[: max(1, min(limit, 100))]]

    def _list_payloads(self, record_type: str, *, actor_id: str) -> list[dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT payload FROM ravan_assistant_records WHERE record_type=%s AND actor_id=%s ORDER BY updated_at DESC", (record_type, actor_id))
                return [dict(row["payload"]) for row in cur.fetchall()]

    def save_action_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = payload.get("created_at") or _now()
        record = {**payload, "intent_id": payload.get("intent_id") or f"intent-{uuid.uuid4().hex[:16]}", "created_at": created_at, "expires_at": payload.get("expires_at") or (datetime.fromisoformat(created_at) + timedelta(minutes=10)).isoformat(), "status": "pending_confirmation"}
        return self._upsert(record_id=record["intent_id"], record_type="action", actor_id=record.get("actor_id"), status="pending_confirmation", payload=record)

    def get_action_intent(self, intent_id: str) -> dict[str, Any] | None:
        return self._fetch_one("action", intent_id)

    def claim_action_intent(self, intent_id: str, *, actor_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    UPDATE ravan_assistant_records
                    SET status='executing', payload=jsonb_set(payload, '{status}', '"executing"'::jsonb), updated_at=NOW()
                    WHERE record_type='action' AND record_id=%s AND actor_id=%s AND status='pending_confirmation'
                    RETURNING payload
                    """,
                    (intent_id, actor_id),
                )
                row = cur.fetchone()
            conn.commit()
        return dict(row["payload"]) if row else None

    def update_action_intent(self, intent_id: str, **updates: Any) -> dict[str, Any] | None:
        record = self.get_action_intent(intent_id)
        if not record:
            return None
        record.update(updates)
        record["updated_at"] = _now()
        return self._upsert(record_id=intent_id, record_type="action", actor_id=record.get("actor_id"), status=record.get("status"), payload=record)
