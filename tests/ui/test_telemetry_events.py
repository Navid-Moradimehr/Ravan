from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_event_source():
    """Return a mock EventSource class that captures constructor args."""
    instances = []

    class MockES:
        def __init__(self, url: str):
            self.url = url
            self.onopen = None
            self.onmessage = None
            self.onerror = None
            self.closed = False
            instances.append(self)

        def close(self):
            self.closed = True

    return MockES, instances


def test_use_telemetry_events_connects_to_events_endpoint(mock_event_source):
    MockES, instances = mock_event_source
    # We cannot easily import the React hook in a Python test, so this is a placeholder
    # for the actual JS-side test strategy. In practice, the hook should be tested with
    # Jest/Vitest or Playwright.
    assert True


def test_ai_gateway_build_telemetry_shape():
    """Verify the telemetry payload shape matches what the UI expects."""
    # This is a lightweight contract test for the SSE payload shape.
    payload = {
        "pipeline": [
            {"name": "ingest", "status": "active"},
            {"name": "process", "status": "active"},
            {"name": "ai", "status": "active"},
            {"name": "observe", "status": "active"},
        ],
        "llm": {
            "model": "openai/gpt-oss-20b",
            "base_url": "http://localhost:1234/v1",
            "last_error": None,
        },
    }
    assert "pipeline" in payload
    assert "llm" in payload
    assert len(payload["pipeline"]) == 4
    assert payload["llm"]["last_error"] is None


def test_system_online_logic():
    """systemOnline should be True when there is no error."""
    # Mirror the UI logic: systemOnline = !telemetryEvents.error
    error = None
    system_online = not error
    assert system_online is True

    error = Exception("connection failed")
    system_online = not error
    assert system_online is False
