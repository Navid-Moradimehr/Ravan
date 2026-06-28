"""Tests for alert acknowledgment workflow."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api_service"))

from alert_manager import AlertManager, AlertState
from rbac import create_user, Role


@pytest.fixture
def alert_mgr():
    return AlertManager()


@pytest.fixture
def sample_user():
    return create_user("u-001", "operator1", Role.OPERATOR)


def test_create_alert(alert_mgr):
    alert = alert_mgr.create_alert(
        asset_id="PUMP-01",
        tag="Temperature",
        severity="critical",
        message="Overheating detected",
        triggered_rules=["temp_high"],
    )
    assert alert["alert_id"].startswith("ALERT-")
    assert alert["state"] == AlertState.ACTIVE
    assert alert["asset_id"] == "PUMP-01"
    assert alert["severity"] == "critical"


def test_acknowledge_alert(alert_mgr, sample_user):
    alert = alert_mgr.create_alert(
        asset_id="PUMP-01", tag="Temperature", severity="warning", message="Test"
    )
    result = alert_mgr.acknowledge_alert(alert["alert_id"], sample_user.user_id, "Checking pump")
    assert result["state"] == AlertState.ACKNOWLEDGED
    assert result["acknowledged_by"] == "operator1"
    assert result["acknowledgment_note"] == "Checking pump"


def test_acknowledge_nonexistent_alert(alert_mgr):
    with pytest.raises(ValueError):
        alert_mgr.acknowledge_alert("ALERT-NONE", "u-001")


def test_acknowledge_already_acknowledged(alert_mgr, sample_user):
    alert = alert_mgr.create_alert(
        asset_id="PUMP-01", tag="Temperature", severity="warning", message="Test"
    )
    alert_mgr.acknowledge_alert(alert["alert_id"], sample_user.user_id)
    with pytest.raises(ValueError):
        alert_mgr.acknowledge_alert(alert["alert_id"], sample_user.user_id)


def test_escalate_alert(alert_mgr, sample_user):
    alert = alert_mgr.create_alert(
        asset_id="PUMP-01", tag="Temperature", severity="critical", message="Test"
    )
    result = alert_mgr.escalate_alert(alert["alert_id"], sample_user.user_id, "Need maintenance team")
    assert result["state"] == AlertState.ESCALATED


def test_resolve_alert(alert_mgr, sample_user):
    alert = alert_mgr.create_alert(
        asset_id="PUMP-01", tag="Temperature", severity="warning", message="Test"
    )
    alert_mgr.acknowledge_alert(alert["alert_id"], sample_user.user_id)
    result = alert_mgr.resolve_alert(alert["alert_id"], sample_user.user_id, "Pump replaced")
    assert result["state"] == AlertState.RESOLVED
    assert result["resolved_by"] == "operator1"
    assert result["resolution_note"] == "Pump replaced"


def test_list_alerts_by_state(alert_mgr, sample_user):
    a1 = alert_mgr.create_alert(asset_id="PUMP-01", tag="T", severity="warning", message="M1")
    a2 = alert_mgr.create_alert(asset_id="PUMP-02", tag="T", severity="critical", message="M2")
    alert_mgr.acknowledge_alert(a1["alert_id"], sample_user.user_id)

    active = alert_mgr.list_alerts(state=AlertState.ACTIVE)
    assert len(active) == 1
    assert active[0]["alert_id"] == a2["alert_id"]

    acked = alert_mgr.list_alerts(state=AlertState.ACKNOWLEDGED)
    assert len(acked) == 1
    assert acked[0]["alert_id"] == a1["alert_id"]


def test_alert_history(alert_mgr, sample_user):
    alert = alert_mgr.create_alert(asset_id="PUMP-01", tag="T", severity="warning", message="M")
    alert_mgr.acknowledge_alert(alert["alert_id"], sample_user.user_id, "Note 1")
    alert_mgr.resolve_alert(alert["alert_id"], sample_user.user_id, "Note 2")

    history = alert_mgr.get_alert_history(alert["alert_id"])
    assert len(history) == 1
    assert history[0]["action"] == "acknowledged"
    assert history[0]["note"] == "Note 1"


def test_alert_statistics(alert_mgr, sample_user):
    alert_mgr.create_alert(asset_id="PUMP-01", tag="T", severity="warning", message="M1")
    a2 = alert_mgr.create_alert(asset_id="PUMP-02", tag="T", severity="critical", message="M2")
    alert_mgr.acknowledge_alert(a2["alert_id"], sample_user.user_id)
    alert_mgr.resolve_alert(a2["alert_id"], sample_user.user_id)

    stats = alert_mgr.get_statistics()
    assert stats["total_alerts"] == 2
    assert stats["by_state"][AlertState.RESOLVED] == 1
    assert stats["acknowledgment_rate"] == 50.0  # 1 acknowledged+resolved out of 2 total


def test_filter_by_asset_and_severity(alert_mgr):
    alert_mgr.create_alert(asset_id="PUMP-01", tag="T", severity="warning", message="M1")
    alert_mgr.create_alert(asset_id="PUMP-01", tag="T", severity="critical", message="M2")
    alert_mgr.create_alert(asset_id="PUMP-02", tag="T", severity="warning", message="M3")

    p1 = alert_mgr.list_alerts(asset_id="PUMP-01")
    assert len(p1) == 2

    critical = alert_mgr.list_alerts(severity="critical")
    assert len(critical) == 1
    assert critical[0]["asset_id"] == "PUMP-01"
