from __future__ import annotations

import asyncio


def test_ui_webhook_registration_attaches_to_alert_runtime(tmp_path, monkeypatch):
    import services.api_service.routers.admin as admin
    from services.api_service.routers.admin import WebhookConfig, register_webhook

    monkeypatch.setattr(admin, "WEBHOOK_STATE_PATH", tmp_path / "webhooks.json")
    admin.webhook_registry.clear()
    admin.webhook_outbound.set_endpoints([])
    result = asyncio.run(register_webhook(WebhookConfig(url="http://example.test/alerts")))

    assert result["status"] == "registered"
    assert admin.webhook_outbound.list_endpoints()[0]["url"] == "http://example.test/alerts"
    assert (tmp_path / "webhooks.json").exists()


def test_notification_webhook_is_runtime_attached_and_email_is_explicitly_deferred(tmp_path, monkeypatch):
    import services.api_service.routers.admin as admin
    from services.api_service.routers.admin import NotificationConfig, register_notification

    monkeypatch.setattr(admin, "NOTIFICATION_STATE_PATH", tmp_path / "notifications.json")
    admin.notification_registry.clear()
    admin.webhook_outbound.set_endpoints([])
    result = asyncio.run(register_notification(NotificationConfig(email="ops@example.test")))

    assert result["delivery_mode"] == "email_requires_operator_apprise_or_smtp_config"
    assert (tmp_path / "notifications.json").exists()
