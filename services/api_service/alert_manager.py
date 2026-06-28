"""Alert acknowledgment workflow with audit trail.

Open-source approach: Simple in-memory store with PostgreSQL persistence option.
Integrates with Apprise for multi-channel notifications (email, Slack, Teams, SMS).
For production, integrate with Prometheus Alertmanager.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from rbac import audit_log, users_db
from notifications import notifier, NotificationPayload, webhook_outbound

try:
    import apprise
    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False


class AlertState:
    """Alert lifecycle states."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertManager:
    """Manage alert lifecycle with acknowledgment workflow."""

    def __init__(self):
        self._alerts: dict[str, dict[str, Any]] = {}
        self._acknowledgments: list[dict[str, Any]] = []

    def create_alert(
        self,
        asset_id: str,
        tag: str,
        severity: str,
        message: str,
        triggered_rules: list[str] | None = None,
        source_event_id: str | None = None,
    ) -> dict[str, Any]:
        alert_id = f"ALERT-{uuid.uuid4().hex[:8].upper()}"
        alert = {
            "alert_id": alert_id,
            "asset_id": asset_id,
            "tag": tag,
            "severity": severity,
            "message": message,
            "triggered_rules": triggered_rules or [],
            "state": AlertState.ACTIVE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged_at": None,
            "acknowledged_by": None,
            "acknowledgment_note": None,
            "escalated_at": None,
            "resolved_at": None,
            "resolved_by": None,
            "resolution_note": None,
            "source_event_id": source_event_id,
        }
        self._alerts[alert_id] = alert

        # Send notification via Apprise + webhook
        notifier.notify(NotificationPayload(
            title=f"Alert {alert_id}: {asset_id}.{tag}",
            body=message,
            severity=severity,
            asset_id=asset_id,
            tag=tag,
            event_id=source_event_id,
        ))
        webhook_outbound.send({
            "event_type": "alarm",
            "alert_id": alert_id,
            "asset_id": asset_id,
            "tag": tag,
            "severity": severity,
            "message": message,
            "triggered_rules": triggered_rules or [],
            "timestamp": alert["created_at"],
        })
        return alert

    def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if alert_id not in self._alerts:
            raise ValueError(f"Alert {alert_id} not found")

        alert = self._alerts[alert_id]
        if alert["state"] == AlertState.ACKNOWLEDGED:
            raise ValueError(f"Alert {alert_id} already acknowledged")

        user = users_db.get(user_id)
        username = user.username if user else user_id

        alert["state"] = AlertState.ACKNOWLEDGED
        alert["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
        alert["acknowledged_by"] = username
        alert["acknowledgment_note"] = note

        self._acknowledgments.append({
            "alert_id": alert_id,
            "action": "acknowledged",
            "user_id": user_id,
            "username": username,
            "timestamp": alert["acknowledged_at"],
            "note": note,
        })

        audit_log.log(user_id, "alert_acknowledged", "alerts", {
            "alert_id": alert_id,
            "asset_id": alert["asset_id"],
            "tag": alert["tag"],
            "severity": alert["severity"],
            "note": note,
        })

        return alert

    def escalate_alert(
        self,
        alert_id: str,
        user_id: str,
        reason: str,
    ) -> dict[str, Any]:
        if alert_id not in self._alerts:
            raise ValueError(f"Alert {alert_id} not found")

        alert = self._alerts[alert_id]
        alert["state"] = AlertState.ESCALATED
        alert["escalated_at"] = datetime.now(timezone.utc).isoformat()

        audit_log.log(user_id, "alert_escalated", "alerts", {
            "alert_id": alert_id,
            "reason": reason,
        })

        return alert

    def resolve_alert(
        self,
        alert_id: str,
        user_id: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if alert_id not in self._alerts:
            raise ValueError(f"Alert {alert_id} not found")

        alert = self._alerts[alert_id]
        user = users_db.get(user_id)
        username = user.username if user else user_id

        alert["state"] = AlertState.RESOLVED
        alert["resolved_at"] = datetime.now(timezone.utc).isoformat()
        alert["resolved_by"] = username
        alert["resolution_note"] = note

        audit_log.log(user_id, "alert_resolved", "alerts", {
            "alert_id": alert_id,
            "asset_id": alert["asset_id"],
            "tag": alert["tag"],
            "note": note,
        })

        return alert

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        return self._alerts.get(alert_id)

    def list_alerts(
        self,
        state: str | None = None,
        asset_id: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        alerts = list(self._alerts.values())
        if state:
            alerts = [a for a in alerts if a["state"] == state]
        if asset_id:
            alerts = [a for a in alerts if a["asset_id"] == asset_id]
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        alerts.sort(key=lambda a: a["created_at"], reverse=True)
        return alerts[:limit]

    def get_alert_history(self, alert_id: str) -> list[dict[str, Any]]:
        return [ack for ack in self._acknowledgments if ack["alert_id"] == alert_id]

    def get_statistics(self) -> dict[str, Any]:
        total = len(self._alerts)
        by_state = {}
        for alert in self._alerts.values():
            state = alert["state"]
            by_state[state] = by_state.get(state, 0) + 1

        return {
            "total_alerts": total,
            "by_state": by_state,
            "acknowledgment_rate": (
                (by_state.get(AlertState.ACKNOWLEDGED, 0) + by_state.get(AlertState.RESOLVED, 0)) / total * 100
                if total > 0 else 0
            ),
            "average_resolution_time_minutes": self._avg_resolution_time(),
        }

    def _avg_resolution_time(self) -> float:
        resolved = [
            a for a in self._alerts.values()
            if a["state"] == AlertState.RESOLVED and a["resolved_at"] and a["created_at"]
        ]
        if not resolved:
            return 0.0

        total_minutes = 0.0
        for alert in resolved:
            created = datetime.fromisoformat(alert["created_at"])
            resolved_dt = datetime.fromisoformat(alert["resolved_at"])
            total_minutes += (resolved_dt - created).total_seconds() / 60

        return round(total_minutes / len(resolved), 2)


# Global alert manager instance
alert_manager = AlertManager()
