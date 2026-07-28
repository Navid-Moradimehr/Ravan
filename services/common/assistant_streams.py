"""Replayable assistant stream events and cancellation signals.

Redis is the production backend.  A process-local fallback keeps standalone
local-first installs usable when the optional stream service is absent.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from typing import Any

try:  # pragma: no cover - exercised in the container integration tests
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - local unit tests do not require Redis
    redis = None


_LOCAL_EVENTS: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
_LOCAL_SEQUENCE: dict[str, int] = defaultdict(int)
_LOCAL_CANCELLED: set[str] = set()
_LOCAL_JOBS: deque[dict[str, Any]] = deque()
_LOCAL_LOCK = asyncio.Lock()


class AssistantStreamBus:
    def __init__(self, url: str | None = None, ttl_seconds: int = 3600) -> None:
        self.url = (url or os.getenv("RAVAN_ASSISTANT_REDIS_URL", "")).strip()
        self.ttl_seconds = max(60, ttl_seconds)
        self._client: Any = None

    @property
    def enabled(self) -> bool:
        return bool(self.url and redis is not None)

    async def _redis(self) -> Any:
        if self._client is None and self.enabled:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    @staticmethod
    def _key(stream_id: str) -> str:
        return f"ravan:assistant:stream:{stream_id}"

    @staticmethod
    def _cancel_key(stream_id: str) -> str:
        return f"ravan:assistant:cancel:{stream_id}"

    @staticmethod
    def _owner_key(stream_id: str) -> str:
        return f"ravan:assistant:owner:{stream_id}"

    @staticmethod
    def _jobs_key() -> str:
        return "ravan:assistant:jobs"

    async def enqueue_job(self, payload: dict[str, Any]) -> None:
        client = await self._redis()
        encoded = json.dumps(payload, ensure_ascii=True)
        if client is not None:
            await client.lpush(self._jobs_key(), encoded)
            return
        async with _LOCAL_LOCK:
            _LOCAL_JOBS.append(payload)

    async def dequeue_job(self, timeout_seconds: int = 5) -> dict[str, Any] | None:
        client = await self._redis()
        if client is not None:
            row = await client.brpop(self._jobs_key(), timeout=max(1, timeout_seconds))
            return json.loads(row[1]) if row else None
        async with _LOCAL_LOCK:
            return _LOCAL_JOBS.popleft() if _LOCAL_JOBS else None

    async def bind_owner(self, stream_id: str, thread_id: str, actor_id: str) -> None:
        value = json.dumps({"thread_id": thread_id, "actor_id": actor_id}, ensure_ascii=True)
        client = await self._redis()
        if client is not None:
            await client.set(self._owner_key(stream_id), value, ex=self.ttl_seconds)
            return
        async with _LOCAL_LOCK:
            _LOCAL_EVENTS.setdefault(self._owner_key(stream_id), [])
            _LOCAL_EVENTS[self._owner_key(stream_id)] = [(value, {"owner": json.loads(value)})]

    async def owner(self, stream_id: str) -> dict[str, str] | None:
        client = await self._redis()
        if client is not None:
            raw = await client.get(self._owner_key(stream_id))
            return json.loads(raw) if raw else None
        async with _LOCAL_LOCK:
            rows = _LOCAL_EVENTS.get(self._owner_key(stream_id), [])
            return rows[-1][1].get("owner") if rows else None

    async def publish(self, stream_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event = {"event": event_type, "data": payload, "stream_id": stream_id}
        client = await self._redis()
        if client is not None:
            event_id = await client.xadd(self._key(stream_id), {"payload": json.dumps(event, ensure_ascii=True)})
            await client.expire(self._key(stream_id), self.ttl_seconds)
            return str(event_id)
        async with _LOCAL_LOCK:
            now = time.time_ns()
            _LOCAL_SEQUENCE[stream_id] += 1
            event_id = f"{now:020d}-{_LOCAL_SEQUENCE[stream_id]:06d}"
            _LOCAL_EVENTS[stream_id].append((event_id, event))
            if len(_LOCAL_EVENTS[stream_id]) > 1000:
                del _LOCAL_EVENTS[stream_id][:-1000]
            return event_id

    async def replay(self, stream_id: str, after_id: str = "-") -> list[tuple[str, dict[str, Any]]]:
        client = await self._redis()
        if client is not None:
            start = f"({after_id}" if after_id not in {"", "-", "0"} else "-"
            rows = await client.xrange(self._key(stream_id), min=start, max="+")
            return [(str(event_id), json.loads(fields["payload"])) for event_id, fields in rows]
        async with _LOCAL_LOCK:
            return [(event_id, event) for event_id, event in _LOCAL_EVENTS.get(stream_id, []) if after_id in {"", "-", "0"} or event_id > after_id]

    async def wait_for_events(self, stream_id: str, after_id: str = "-", timeout_seconds: float = 1.0) -> list[tuple[str, dict[str, Any]]]:
        client = await self._redis()
        if client is not None:
            start = after_id if after_id not in {"", "-", "0"} else "0-0"
            rows = await client.xread({self._key(stream_id): start}, count=50, block=max(1, int(timeout_seconds * 1000)))
            if not rows:
                return []
            return [(str(event_id), json.loads(fields["payload"])) for _, entries in rows for event_id, fields in entries]
        await asyncio.sleep(timeout_seconds)
        return await self.replay(stream_id, after_id)

    async def cancel(self, stream_id: str) -> None:
        client = await self._redis()
        if client is not None:
            await client.set(self._cancel_key(stream_id), "1", ex=self.ttl_seconds)
            return
        async with _LOCAL_LOCK:
            _LOCAL_CANCELLED.add(stream_id)

    async def is_cancelled(self, stream_id: str) -> bool:
        client = await self._redis()
        if client is not None:
            return bool(await client.exists(self._cancel_key(stream_id)))
        async with _LOCAL_LOCK:
            return stream_id in _LOCAL_CANCELLED

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


stream_bus = AssistantStreamBus()
