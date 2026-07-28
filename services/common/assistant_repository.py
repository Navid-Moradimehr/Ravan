"""Assistant repository factory and storage selection contract."""

from __future__ import annotations

import os

from services.common.assistant_store import AssistantStore


def build_assistant_store():
    backend = os.getenv("RAVAN_ASSISTANT_STORE_BACKEND", "json").strip().lower()
    cache_key = (backend, os.getenv("RAVAN_ASSISTANT_STORE_PATH", ""), os.getenv("TIMESCALE_HOST", ""), os.getenv("TIMESCALE_DB", ""))
    cached = _STORE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if backend in {"json", "file", "local"}:
        store = AssistantStore()
        _STORE_CACHE[cache_key] = store
        return store
    if backend in {"postgres", "postgresql"}:
        from services.common.postgres_assistant_store import PostgresAssistantStore

        store = PostgresAssistantStore()
        _STORE_CACHE[cache_key] = store
        return store
    raise ValueError(f"unsupported RAVAN_ASSISTANT_STORE_BACKEND: {backend}")


_STORE_CACHE: dict[tuple[str, str, str, str], object] = {}
