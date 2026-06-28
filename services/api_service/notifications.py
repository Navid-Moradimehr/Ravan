"""Notification service using Apprise for multi-channel alerts.

Apprise supports 100+ notification services including:
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


notifier = AppriseNotifier(_load_urls_from_env())
