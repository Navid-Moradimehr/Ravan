from __future__ import annotations


def test_assistant_repository_defaults_to_local_store(monkeypatch, tmp_path):
    monkeypatch.delenv("RAVAN_ASSISTANT_STORE_BACKEND", raising=False)
    monkeypatch.setenv("RAVAN_ASSISTANT_STORE_PATH", str(tmp_path / "assistant.json"))
    from services.common.assistant_repository import build_assistant_store
    from services.common.assistant_store import AssistantStore

    assert isinstance(build_assistant_store(), AssistantStore)


def test_assistant_repository_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("RAVAN_ASSISTANT_STORE_BACKEND", "unknown")
    from services.common.assistant_repository import build_assistant_store

    try:
        build_assistant_store()
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unknown assistant backend should fail clearly")
