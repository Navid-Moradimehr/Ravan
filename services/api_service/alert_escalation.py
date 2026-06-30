"""Alert escalation rules engine.

Open-source approach: Configurable rules with time-based escalation.
For production, integrate with Prometheus Alertmanager for routing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

try:
    from alert_manager import alert_manager, AlertState
except ImportError:
    from services.api_service.alert_manager import alert_manager, AlertState  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class EscalationRule:
    """A rule for escalating alerts based on conditions."""
    rule_id: str
    name: str
    description: str = ""
    # Conditions
    severity_filter: list[str] = field(default_factory=lambda: ["critical"])
    asset_pattern: str | None = None  # Regex pattern for asset matching
    tag_pattern: str | None = None
    # Timing
    auto_escalate_after_minutes: int = 15
    auto_resolve_after_minutes: int | None = None
    # Actions
    notify_channels: list[str] = field(default_factory=list)
    escalate_to_role: str | None = None
    # State
    enabled: bool = True


class EscalationEngine:
    """Engine for processing alert escalation rules."""

    def __init__(self):
        self._rules: dict[str, EscalationRule] = {}
        self._handlers: list[Callable[[dict[str, Any]], None]] = []

    def add_rule(self, rule: EscalationRule) -> None:
        """Add an escalation rule."""
        self._rules[rule.rule_id] = rule
        logger.info(f"Added escalation rule: {rule.name}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an escalation rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def list_rules(self) -> list[dict[str, Any]]:
        """List all escalation rules."""
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "severity_filter": r.severity_filter,
                "auto_escalate_after_minutes": r.auto_escalate_after_minutes,
                "enabled": r.enabled,
            }
            for r in self._rules.values()
        ]

    def register_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register a handler for escalation events."""
        self._handlers.append(handler)

    def process_alert(self, alert: dict[str, Any]) -> list[dict[str, Any]]:
        """Process an alert against all rules. Returns triggered actions."""
        triggered = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            if not self._matches_rule(alert, rule):
                continue

            # Check if auto-escalation time has passed
            created = datetime.fromisoformat(alert.get("created_at", "").replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - created).total_seconds() / 60

            if elapsed >= rule.auto_escalate_after_minutes:
                action = {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.name,
                    "action": "escalate",
                    "alert_id": alert["alert_id"],
                    "reason": f"Auto-escalated after {rule.auto_escalate_after_minutes} minutes",
                    "notify_channels": rule.notify_channels,
                    "escalate_to_role": rule.escalate_to_role,
                }
                triggered.append(action)

                # Execute escalation
                self._execute_escalation(alert, action)

        return triggered

    def _matches_rule(self, alert: dict[str, Any], rule: EscalationRule) -> bool:
        """Check if an alert matches a rule's conditions."""
        # Severity filter
        if alert.get("severity") not in rule.severity_filter:
            return False

        # Asset pattern
        if rule.asset_pattern and alert.get("asset_id"):
            import re
            if not re.search(rule.asset_pattern, alert.get("asset_id", "")):
                return False

        # Tag pattern
        if rule.tag_pattern and alert.get("tag"):
            import re
            if not re.search(rule.tag_pattern, alert.get("tag", "")):
                return False

        return True

    def _execute_escalation(self, alert: dict[str, Any], action: dict[str, Any]) -> None:
        """Execute escalation actions."""
        # Update alert state
        try:
            alert_manager.escalate_alert(
                alert["alert_id"],
                "system",
                action["reason"],
            )
        except ValueError:
            pass  # Already escalated

        # Notify handlers
        for handler in self._handlers:
            try:
                handler(action)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    def check_all_pending_alerts(self) -> list[dict[str, Any]]:
        """Check all pending alerts for escalation."""
        all_actions = []
        pending = alert_manager.list_alerts(state=AlertState.ACTIVE)
        for alert in pending:
            actions = self.process_alert(alert)
            all_actions.extend(actions)
        return all_actions

    def get_default_rules(self) -> list[EscalationRule]:
        """Get default escalation rules."""
        return [
            EscalationRule(
                rule_id="escalate-critical-15min",
                name="Escalate Critical After 15 Minutes",
                description="Automatically escalate critical alerts that haven't been acknowledged",
                severity_filter=["critical"],
                auto_escalate_after_minutes=15,
                notify_channels=["email", "slack"],
                escalate_to_role="admin",
            ),
            EscalationRule(
                rule_id="escalate-warning-1hour",
                name="Escalate Warning After 1 Hour",
                description="Escalate warning alerts after 1 hour",
                severity_filter=["warning"],
                auto_escalate_after_minutes=60,
                notify_channels=["email"],
                escalate_to_role="operator",
            ),
            EscalationRule(
                rule_id="auto-resolve-24hours",
                name="Auto-Resolve After 24 Hours",
                description="Automatically resolve stale alerts",
                severity_filter=["warning", "critical"],
                auto_escalate_after_minutes=1440,
                auto_resolve_after_minutes=1440,
                notify_channels=["email"],
            ),
        ]


# Global escalation engine
escalation_engine = EscalationEngine()

# Load default rules
for rule in escalation_engine.get_default_rules():
    escalation_engine.add_rule(rule)
