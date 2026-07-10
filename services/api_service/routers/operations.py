from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.analytics.correlation import get_analyzer
from services.analytics.kpi_engine import KPIFormula, kpi_engine
from services.api_service.alert_escalation import EscalationRule, escalation_engine
from services.api_service.alert_manager import alert_manager
from services.api_service.notifications import APPRISE_AVAILABLE, NotificationPayload, notifier
from services.api_service.ops_runtime import (
    get_outbound_bridge_state,
    publish_outbound_event,
    set_outbound_bridge_enabled,
    set_outbound_bridge_state,
)

router = APIRouter(tags=["operations"])


class AlertCreateRequest(BaseModel):
    asset_id: str
    tag: str
    severity: str
    message: str
    triggered_rules: list[str] = Field(default_factory=list)
    source_event_id: str | None = None


class AlertAcknowledgeRequest(BaseModel):
    alert_id: str
    user_id: str
    note: str | None = None


class AlertEscalateRequest(BaseModel):
    alert_id: str
    user_id: str
    reason: str


class AlertResolveRequest(BaseModel):
    alert_id: str
    user_id: str
    note: str | None = None


class NotifyRequest(BaseModel):
    title: str
    body: str
    severity: str = "info"
    asset_id: str | None = None
    tag: str | None = None
    event_id: str | None = None


class CorrelationRequest(BaseModel):
    tag: str
    timestamp: str
    value: float


class EscalationRuleRequest(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    severity_filter: list[str] = Field(default_factory=lambda: ["critical"])
    asset_pattern: str | None = None
    tag_pattern: str | None = None
    auto_escalate_after_minutes: int = 15
    notify_channels: list[str] = Field(default_factory=list)
    escalate_to_role: str | None = None
    enabled: bool = True


class KPIRequest(BaseModel):
    kpi_id: str
    name: str
    description: str = ""
    input_tags: list[str] = Field(default_factory=list)
    expression: str = ""
    window_seconds: int = 60
    unit: str = ""
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    enabled: bool = True


class OutboundBridgeConfig(BaseModel):
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_use_tls: bool = False
    mqtt_topic_template: str = "industrial/{{asset_id}}/{{tag}}"
    amqp_url: str | None = None
    amqp_exchange: str = "industrial.events"
    amqp_routing_key: str = "{{asset_id}}.{{tag}}"


class OutboundBridgeState(BaseModel):
    enabled: bool = True
    config: OutboundBridgeConfig


class OutboundEventRequest(BaseModel):
    asset_id: str
    tag: str
    value: float
    quality: str = "good"
    unit: str = ""
    timestamp: str | None = None


@router.post("/api/v1/alerts")
async def create_alert(req: AlertCreateRequest) -> dict[str, Any]:
    try:
        return alert_manager.create_alert(
            asset_id=req.asset_id,
            tag=req.tag,
            severity=req.severity,
            message=req.message,
            triggered_rules=req.triggered_rules,
            source_event_id=req.source_event_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/alerts/acknowledge")
async def acknowledge_alert(req: AlertAcknowledgeRequest) -> dict[str, Any]:
    try:
        return alert_manager.acknowledge_alert(req.alert_id, req.user_id, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/alerts/escalate")
async def escalate_alert(req: AlertEscalateRequest) -> dict[str, Any]:
    try:
        return alert_manager.escalate_alert(req.alert_id, req.user_id, req.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/alerts/resolve")
async def resolve_alert(req: AlertResolveRequest) -> dict[str, Any]:
    try:
        return alert_manager.resolve_alert(req.alert_id, req.user_id, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v1/alerts")
async def list_alerts(
    state: str | None = None,
    asset_id: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return alert_manager.list_alerts(state=state, asset_id=asset_id, severity=severity, limit=limit)


@router.get("/api/v1/alerts/statistics")
async def get_alert_statistics() -> dict[str, Any]:
    return alert_manager.get_statistics()


@router.get("/api/v1/alerts/{alert_id}")
async def get_alert(alert_id: str) -> dict[str, Any]:
    alert = alert_manager.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.get("/api/v1/alerts/{alert_id}/history")
async def get_alert_history(alert_id: str) -> list[dict[str, Any]]:
    return alert_manager.get_alert_history(alert_id)


@router.post("/api/v1/notifications/send")
async def send_notification(req: NotifyRequest) -> dict[str, Any]:
    payload = NotificationPayload(
        title=req.title,
        body=req.body,
        severity=req.severity,
        asset_id=req.asset_id,
        tag=req.tag,
        event_id=req.event_id,
    )
    result = notifier.notify(payload)
    if not result["sent"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Notification failed"))
    return result


@router.get("/api/v1/notifications/status")
async def notification_status() -> dict[str, Any]:
    from services.api_service.delivery_ledger import recent_deliveries
    return {
        "apprise_available": APPRISE_AVAILABLE,
        "channels_configured": len(notifier._config_urls),
        "channels": notifier._config_urls,
        "recent_deliveries": recent_deliveries(),
    }


@router.post("/api/v1/analytics/correlation/ingest")
async def ingest_correlation_data(req: CorrelationRequest) -> dict[str, str]:
    analyzer = get_analyzer()
    analyzer.add_value(req.tag, req.timestamp, req.value)
    return {"status": "ok"}


@router.get("/api/v1/analytics/correlation/matrix")
async def get_correlation_matrix() -> dict[str, Any]:
    return get_analyzer().get_correlation_matrix()


@router.get("/api/v1/analytics/correlation/strong")
async def get_strong_correlations(threshold: float = 0.7) -> list[dict[str, Any]]:
    return get_analyzer().find_strong_correlations(threshold)


@router.get("/api/v1/analytics/correlation/graph")
async def get_causal_graph(threshold: float = 0.5) -> dict[str, Any]:
    return get_analyzer().build_causal_graph(threshold)


@router.get("/api/v1/analytics/correlation/propagation/{tag}")
async def get_anomaly_propagation(tag: str, lookback: int = 10) -> list[dict[str, Any]]:
    return get_analyzer().detect_anomaly_propagation(tag, lookback)


@router.post("/api/v1/alerts/escalation/rules")
async def add_escalation_rule(req: EscalationRuleRequest) -> dict[str, str]:
    rule = EscalationRule(
        rule_id=req.rule_id,
        name=req.name,
        description=req.description,
        severity_filter=req.severity_filter,
        asset_pattern=req.asset_pattern,
        tag_pattern=req.tag_pattern,
        auto_escalate_after_minutes=req.auto_escalate_after_minutes,
        notify_channels=req.notify_channels,
        escalate_to_role=req.escalate_to_role,
        enabled=req.enabled,
    )
    escalation_engine.add_rule(rule)
    return {"status": "ok", "rule_id": req.rule_id}


@router.get("/api/v1/alerts/escalation/rules")
async def list_escalation_rules() -> list[dict[str, Any]]:
    return escalation_engine.list_rules()


@router.delete("/api/v1/alerts/escalation/rules/{rule_id}")
async def delete_escalation_rule(rule_id: str) -> dict[str, str]:
    if escalation_engine.remove_rule(rule_id):
        return {"status": "deleted", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")


@router.post("/api/v1/alerts/escalation/check")
async def check_escalations() -> list[dict[str, Any]]:
    return escalation_engine.check_all_pending_alerts()


@router.post("/api/v1/kpis")
async def register_kpi(req: KPIRequest) -> dict[str, str]:
    kpi = KPIFormula(
        kpi_id=req.kpi_id,
        name=req.name,
        description=req.description,
        input_tags=req.input_tags,
        expression=req.expression,
        window_seconds=req.window_seconds,
        unit=req.unit,
        warning_threshold=req.warning_threshold,
        critical_threshold=req.critical_threshold,
        enabled=req.enabled,
    )
    kpi_engine.register_kpi(kpi)
    return {"status": "ok", "kpi_id": req.kpi_id}


@router.get("/api/v1/kpis")
async def list_kpis() -> list[dict[str, Any]]:
    return kpi_engine.list_kpis()


@router.delete("/api/v1/kpis/{kpi_id}")
async def unregister_kpi(kpi_id: str) -> dict[str, str]:
    if kpi_engine.unregister_kpi(kpi_id):
        return {"status": "deleted", "kpi_id": kpi_id}
    raise HTTPException(status_code=404, detail="KPI not found")


@router.post("/api/v1/kpis/ingest")
async def ingest_kpi_value(tag: str, value: float) -> list[dict[str, Any]]:
    return kpi_engine.ingest_value(tag, value)


@router.get("/api/v1/kpis/samples")
async def get_sample_kpis() -> list[dict[str, Any]]:
    return [k.__dict__ for k in kpi_engine.get_sample_kpis()]


@router.post("/api/v1/outbound-bridge/config")
async def set_bridge_config(req: OutboundBridgeState) -> dict[str, Any]:
    return set_outbound_bridge_state(req)


@router.get("/api/v1/outbound-bridge/config")
async def get_bridge_config() -> dict[str, Any]:
    return get_outbound_bridge_state()


@router.post("/api/v1/outbound-bridge/publish")
async def publish_bridge_event(req: OutboundEventRequest) -> dict[str, Any]:
    try:
        return publish_outbound_event(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/outbound-bridge/enable")
async def enable_bridge(enabled: bool = True) -> dict[str, Any]:
    try:
        return set_outbound_bridge_enabled(enabled)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
