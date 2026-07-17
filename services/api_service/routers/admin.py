from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.api_service.auth import decode_access_token, require_permission
from services.api_service.collaboration import collaboration_store
from services.api_service.rbac import Permission
from services.api_service.runtime import _to_legacy_iot_event
from services.api_service.notifications import notifier, webhook_outbound

router = APIRouter(tags=["admin"])


class WebhookConfig(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["alarm", "anomaly"])
    headers: dict[str, str] = Field(default_factory=dict)


class NotificationConfig(BaseModel):
    email: str | None = None
    webhook_url: str | None = None
    slack_webhook: str | None = None
    teams_webhook: str | None = None
    apprise_url: str | None = None
    events: list[str] = Field(default_factory=lambda: ["alarm", "anomaly"])


class CreateUserRequest(BaseModel):
    user_id: str
    username: str
    role: str
    email: str | None = None
    password: str | None = None


class AuthRequest(BaseModel):
    username: str
    password: str


webhook_registry: dict[str, WebhookConfig] = {}
notification_registry: dict[str, NotificationConfig] = {}
WEBHOOK_STATE_PATH = Path(os.getenv("DATASTREAM_WEBHOOK_REGISTRY_PATH", ".datastream/webhooks.json"))
NOTIFICATION_STATE_PATH = Path(os.getenv("DATASTREAM_NOTIFICATION_REGISTRY_PATH", ".datastream/notifications.json"))


def _persist_registry(path: Path, values: dict[str, BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({key: value.model_dump() for key, value in values.items()}, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _load_registries() -> None:
    if WEBHOOK_STATE_PATH.exists():
        payload = json.loads(WEBHOOK_STATE_PATH.read_text(encoding="utf-8"))
        webhook_registry.update({key: WebhookConfig.model_validate(value) for key, value in payload.items()})
        endpoints = webhook_outbound.list_endpoints()
        existing_urls = {str(item.get("url")) for item in endpoints}
        endpoints.extend(config.model_dump() for config in webhook_registry.values() if config.url not in existing_urls)
        webhook_outbound.set_endpoints(endpoints)
    if NOTIFICATION_STATE_PATH.exists():
        payload = json.loads(NOTIFICATION_STATE_PATH.read_text(encoding="utf-8"))
        notification_registry.update({key: NotificationConfig.model_validate(value) for key, value in payload.items()})


_load_registries()


@router.post("/api/v1/webhooks")
async def register_webhook(config: WebhookConfig) -> dict[str, str]:
    import uuid

    hook_id = str(uuid.uuid4())[:8]
    webhook_registry[hook_id] = config
    webhook_outbound.add_endpoint(config.url, config.events, config.headers)
    _persist_registry(WEBHOOK_STATE_PATH, webhook_registry)
    return {"id": hook_id, "status": "registered"}


@router.get("/api/v1/webhooks")
async def list_webhooks() -> dict[str, Any]:
    return {"webhooks": {k: v.model_dump() for k, v in webhook_registry.items()}}


@router.delete("/api/v1/webhooks/{hook_id}")
async def delete_webhook(hook_id: str) -> dict[str, str]:
    config = webhook_registry.pop(hook_id, None)
    if config is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhook_outbound.remove_endpoint(config.url)
    _persist_registry(WEBHOOK_STATE_PATH, webhook_registry)
    return {"status": "deleted"}


@router.post("/api/v1/notifications")
async def register_notification(config: NotificationConfig) -> dict[str, Any]:
    import uuid

    notif_id = str(uuid.uuid4())[:8]
    notification_registry[notif_id] = config
    delivery_mode = "metadata_only"
    if config.webhook_url:
        webhook_outbound.add_endpoint(config.webhook_url, config.events)
        delivery_mode = "webhook"
    if config.apprise_url:
        if notifier.add_channel(config.apprise_url):
            delivery_mode = "apprise"
        else:
            delivery_mode = "apprise_unavailable"
    if config.email and not config.apprise_url:
        delivery_mode = "email_requires_operator_apprise_or_smtp_config"
    _persist_registry(NOTIFICATION_STATE_PATH, notification_registry)
    return {"id": notif_id, "status": "registered", "delivery_mode": delivery_mode}


@router.get("/api/v1/notifications")
async def list_notifications() -> dict[str, Any]:
    return {"notifications": {k: v.model_dump() for k, v in notification_registry.items()}}


@router.delete("/api/v1/notifications/{notification_id}")
async def delete_notification(notification_id: str) -> dict[str, str]:
    config = notification_registry.pop(notification_id, None)
    if config is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if config.webhook_url:
        webhook_outbound.remove_endpoint(config.webhook_url)
    if config.apprise_url:
        notifier.remove_channel(config.apprise_url)
    _persist_registry(NOTIFICATION_STATE_PATH, notification_registry)
    return {"status": "deleted", "notification_id": notification_id}


@router.post("/api/v1/webhooks/test/{hook_id}")
async def test_webhook(hook_id: str) -> dict[str, str]:
    if hook_id not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    config = webhook_registry[hook_id]
    payload = {
        "event": "test",
        "message": "Webhook test from Ravan",
        "timestamp": "2024-01-01T00:00:00Z",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(config.url, json=payload, headers=config.headers, timeout=10.0)
            return {"status": "sent", "http_status": str(resp.status_code)}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}


@router.get("/api/v1/annotations")
async def list_annotations(target_type: str | None = None, target_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return collaboration_store.list_annotations(target_type, target_id, limit)


@router.post("/api/v1/annotations")
async def create_annotation(req: dict[str, Any]) -> dict[str, str]:
    ann = collaboration_store.add_annotation(
        target_type=req.get("target_type", "event"),
        target_id=req.get("target_id", ""),
        user_id=req.get("user_id", "anonymous"),
        username=req.get("username", "Anonymous"),
        text=req.get("text", ""),
        tags=req.get("tags", []),
    )
    return {"status": "created", "annotation_id": ann.annotation_id}


@router.delete("/api/v1/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str) -> dict[str, str]:
    collaboration_store.delete_annotation(annotation_id)
    return {"status": "deleted"}


@router.post("/api/v1/users")
async def create_user_endpoint(
    req: CreateUserRequest,
    _admin: Any = Depends(require_permission(Permission.ADMIN)),
) -> dict[str, Any]:
    from services.api_service.auth import create_user
    from services.api_service.rbac import Role

    role = Role(req.role)
    user = create_user(req.user_id, req.username, role, req.email, req.password)
    return user.to_dict()


@router.get("/api/v1/users/{user_id}")
async def get_user_endpoint(
    user_id: str,
    _admin: Any = Depends(require_permission(Permission.ADMIN)),
) -> dict[str, Any]:
    from services.api_service.auth import get_user

    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()


@router.post("/api/v1/auth/login")
async def login(req: AuthRequest) -> dict[str, Any]:
    from services.api_service.auth import authenticate_user, create_access_token, audit_log

    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    audit_log.log(user.user_id, "login", "auth")
    token = create_access_token(user.user_id, user.role.value)
    return {"token": token, "user": user.to_dict()}


@router.get("/api/v1/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    _admin: Any = Depends(require_permission(Permission.ADMIN)),
) -> list[dict[str, Any]]:
    from services.api_service.auth import audit_log

    return audit_log.get_logs(limit)
