from __future__ import annotations

from services.common.connection_diagnostics import run_connection_test
from services.common.connection_registry import SourceConnection


def test_diagnostics_does_not_require_network_for_mock_source():
    result = run_connection_test(SourceConnection("mock-1", "Mock", "mock", "demo-site"))
    assert result["valid"] is True
    assert result["network_test"] == "not_required"


def test_diagnostics_reports_unreachable_tcp_source():
    result = run_connection_test(SourceConnection("mqtt-1", "MQTT", "mqtt", "demo-site", "mqtt://127.0.0.1:1"), timeout_seconds=0.1)
    assert result["valid"] is True
    assert result["network_test"] in {"unreachable", "timeout"}


def test_diagnostics_reports_rest_activation_and_network_state():
    result = run_connection_test(SourceConnection("rest-1", "REST", "rest", "demo-site", "https://example.test/api"))
    assert result["valid"] is True
    assert result["activation_ready"] is False
    assert result["network_test"] in {"reachable", "unreachable", "timeout", "unhealthy"}
