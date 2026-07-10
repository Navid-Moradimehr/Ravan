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

    def add_channel(self, url: str) -> bool:
        """Add a notification channel (e.g., slack://token@channel)."""
        if not APPRISE_AVAILABLE:
            return False
        try:
            if self._apprise is None:
                self._apprise = apprise.Apprise()
            self._apprise.add(url)
            self._config_urls.append(url)
            return True
        except Exception as e:
            logger.error(f"Failed to add channel {url}: {e}")
            return False

    def remove_channel(self, url: str) -> bool:
        if url not in self._config_urls:
            return False
        self._config_urls.remove(url)
        if self._apprise is not None:
            self._apprise = apprise.Apprise()
            for channel in self._config_urls:
                self._apprise.add(channel)
        return True

class WebhookOutbound:
    """Generic HTTP webhook outbound for alarms/events."""

    def __init__(self, endpoints: list[dict[str, Any]] | None = None, max_retries: int = 3):
        self._endpoints = endpoints or []
        self._session: Any = None
        self._max_retries = max_retries
        self._backoff_seconds = (0.5, 1.5, 4.0)

    def _get_session(self) -> Any:
        if self._session is None:
            import httpx
            self._session = httpx.Client(timeout=10.0, transport=httpx.HTTPTransport(retries=0))
        return self._session

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST payload to all configured webhook endpoints.

        Retries transient failures (connection errors, 5xx, 429) with exponential
        backoff up to max_retries so transient network blips don't drop alerts.
        """
        import time as _time
        results = []
        session = self._get_session()
        for endpoint in self._endpoints:
            url = endpoint.get("url")
            headers = endpoint.get("headers", {})
            events = endpoint.get("events", ["alarm", "anomaly"])
            event_type = payload.get("event_type", "alarm")
            if event_type not in events:
                continue
            attempt = 0
            last_error: str | None = None
            status = 0
            while True:
                try:
                    resp = session.post(url, json=payload, headers=headers)
                    status = resp.status_code
                    ok = status < 400
                    retryable = status == 429 or status >= 500
                    if ok or not retryable or attempt >= self._max_retries:
                        results.append({"url": url, "status": status, "ok": ok, "attempts": attempt + 1})
                        break
                    last_error = f"http_{status}"
                except Exception as e:
                    last_error = str(e)
                    if attempt >= self._max_retries:
                        results.append({"url": url, "status": status, "ok": False, "attempts": attempt + 1, "error": last_error})
                        break
                attempt += 1
                backoff = self._backoff_seconds[min(attempt - 1, len(self._backoff_seconds) - 1)]
                _time.sleep(backoff)
        return {"sent": any(r["ok"] for r in results), "results": results}

    def add_endpoint(self, url: str, events: list[str] | None = None, headers: dict[str, str] | None = None) -> None:
        self._endpoints.append({"url": url, "events": events or ["alarm", "anomaly"], "headers": headers or {}})

    def remove_endpoint(self, url: str) -> bool:
        for i, ep in enumerate(self._endpoints):
            if ep.get("url") == url:
                self._endpoints.pop(i)
                return True
        return False

    def list_endpoints(self) -> list[dict[str, Any]]:
        return list(self._endpoints)

    def set_endpoints(self, endpoints: list[dict[str, Any]]) -> None:
        self._endpoints = list(endpoints)

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
