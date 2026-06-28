"""Notification service using Apprise for multi-channel alerts.

Apprise supports 100+ notification services including:
- Generic webhook outbound (HTTP POST)
- Email (SMTP, SendGrid, AWS SES)
- Slack, Discord, Teams, Telegram
- Webhooks (generic)
- SMS (Twilio, AWS SNS)
- Desktop notifications

Open-source: https://github.com/caronc/apprise
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Try to import apprise, but make it optional
try:
    import apprise
    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False
    logger.warning("Apprise not installed. Notifications will be logged only.")


class NotificationPayload(BaseModel):
    title: str
    body: str
    severity: str = "info"
    asset_id: str | None = None
    tag: str | None = None
    event_id: str | None = None


class AppriseNotifier:
    """Multi-channel notification service using Apprise."""

    def __init__(self, config_urls: list[str] | None = None):
        self._apprise: Any = None
        self._config_urls = config_urls or []

        if APPRISE_AVAILABLE and self._config_urls:
            self._apprise = apprise.Apprise()
            for url in self._config_urls:
                self._apprise.add(url)

    def notify(self, payload: NotificationPayload) -> dict[str, Any]:
        """Send notification through all configured channels."""
        result = {
            "sent": False,
            "channels": len(self._config_urls),
            "error": None,
        }

        if not APPRISE_AVAILABLE:
            logger.info(f"[NOTIFICATION] {payload.severity.upper()}: {payload.title} - {payload.body}")
            result["sent"] = True
            result["mode"] = "logged"
            return result

        if not self._apprise:
            result["error"] = "No notification channels configured"
            return result

        try:
            # Format based on severity
            prefix = {
                "critical": "🚨 CRITICAL",
                "warning": "⚠️ WARNING",
                "info": "ℹ️ INFO",
            }.get(payload.severity, payload.severity.upper())

            title = f"{prefix}: {payload.title}"
            body = payload.body

            if payload.asset_id:
                body += f"\nAsset: {payload.asset_id}"
            if payload.tag:
                body += f"\nTag: {payload.tag}"
            if payload.event_id:
                body += f"\nEvent: {payload.event_id}"

            self._apprise.notify(title=title, body=body)
            result["sent"] = True
            result["mode"] = "apprise"
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            result["error"] = str(e)

        return result

class WebhookOutbound:
    """Generic HTTP webhook outbound for alarms/events."""

    def __init__(self, endpoints: list[dict[str, Any]] | None = None):
        self._endpoints = endpoints or []
        self._session: Any = None

    def _get_session(self) -> Any:
        if self._session is None:
            import httpx
            self._session = httpx.Client(timeout=10.0)
        return self._session

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST payload to all configured webhook endpoints."""
        results = []
        session = self._get_session()
        for endpoint in self._endpoints:
            url = endpoint.get("url")
            headers = endpoint.get("headers", {})
            events = endpoint.get("events", ["alarm", "anomaly"])
            event_type = payload.get("event_type", "alarm")
            if event_type not in events:
                continue
            try:
                resp = session.post(url, json=payload, headers=headers)
                results.append({"url": url, "status": resp.status_code, "ok": resp.status_code < 400})
            except Exception as e:
                results.append({"url": url, "status": 0, "ok": False, "error": str(e)})
        return {"sent": any(r["ok"] for r in results), "results": results}

    def add_endpoint(self, url: str, events: list[str] | None = None, headers: dict[str, str] | None = None) -> None:
        self._endpoints.append({"url": url, "events": events or ["alarm", "anomaly"], "headers": headers or {}})

    def remove_endpoint(self, url: str) -> bool:
        for i, ep in enumerate(self._endpoints):
            if ep.get("url") == url:
                self._endpoints.pop(i)
                return True
        return False

def _load_webhooks_from_env() -> list[dict[str, Any]]:
    """Load webhook endpoints from WEBHOOK_URLS env var."""
    import os, json
    raw = os.getenv("WEBHOOK_URLS", "")
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [{"url": u.strip(), "events": ["alarm", "anomaly"]} for u in raw.split(",") if u.strip()]


    def add_channel(self, url: str) -> bool:
        """Add a notification channel (e.g., slack://token@channel)."""
        if not APPRISE_AVAILABLE:
            return False

        try:
            self._apprise.add(url)
            self._config_urls.append(url)
            return True
        except Exception as e:
            logger.error(f"Failed to add channel {url}: {e}")
            return False


# Global notifier instance (initialized with env var URLs)
def _load_urls_from_env() -> list[str]:
    """Load Apprise URLs from environment variable."""
    urls = []
    # Comma-separated list of apprise URLs
    env_urls = __import__("os").getenv("APPRISE_URLS", "")
    if env_urls:
        urls = [u.strip() for u in env_urls.split(",") if u.strip()]
    return urls


# Global webhook outbound instance
webhook_outbound = WebhookOutbound(_load_webhooks_from_env())

notifier = AppriseNotifier(_load_urls_from_env())
