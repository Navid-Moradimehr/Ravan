"""Assistant repository factory and storage selection contract."""

from __future__ import annotations

import os

from services.common.assistant_store import AssistantStore


def build_assistant_store():
    backend = os.getenv("RAVAN_ASSISTANT_STORE_BACKEND", "json").strip().lower()
    if backend in {"json", "file", "local"}:
        return AssistantStore()
    if backend in {"postgres", "postgresql"}:
        from services.common.postgres_assistant_store import PostgresAssistantStore

        return PostgresAssistantStore()
    raise ValueError(f"unsupported RAVAN_ASSISTANT_STORE_BACKEND: {backend}")
