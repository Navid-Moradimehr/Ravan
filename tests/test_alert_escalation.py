"""Tests for alert escalation engine."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api_service"))

from alert_escalation import EscalationEngine, EscalationRule
from alert_manager import AlertManager, AlertState


@pytest.fixture
def engine():
    return EscalationEngine()


@pytest.fixture
def alert_mgr():
    return AlertManager()


def test_add_rule(engine):
    rule = EscalationRule(
        rule_id="test-1",
        name="Test Rule",
        severity_filter=["critical"],
        auto_escalate_after_minutes=5,
    )
    engine.add_rule(rule)
    assert "test-1" in engine._rules


def test_remove_rule(engine):
    rule = EscalationRule(rule_id="test-2", name="Test Rule 2")
    engine.add_rule(rule)
    assert engine.remove_rule("test-2") is True
    assert engine.remove_rule("test-2") is False


def test_list_rules(engine):
    rule = EscalationRule(rule_id="test-3", name="Test Rule 3")
    engine.add_rule(rule)
    rules = engine.list_rules()
    assert len(rules) == 1
    assert rules[0]["rule_id"] == "test-3"


def test_matches_rule(engine):
    rule = EscalationRule(
        rule_id="test",
        name="Test",
        severity_filter=["critical"],
        asset_pattern="PUMP-.*",
    )
    
    assert engine._matches_rule({"severity": "critical", "asset_id": "PUMP-01"}, rule) is True
    assert engine._matches_rule({"severity": "warning", "asset_id": "PUMP-01"}, rule) is False
    assert engine._matches_rule({"severity": "critical", "asset_id": "VALVE-01"}, rule) is False


def test_default_rules(engine):
    rules = engine.get_default_rules()
    assert len(rules) >= 3
    assert any(r.rule_id == "escalate-critical-15min" for r in rules)
    assert any(r.rule_id == "escalate-warning-1hour" for r in rules)
