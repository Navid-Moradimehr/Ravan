from __future__ import annotations

import importlib


def test_collaboration_store_persists_and_recovers_state(tmp_path, monkeypatch):
    state_path = tmp_path / "collaboration-store.json"
    monkeypatch.setenv("COLLABORATION_STORE_PATH", str(state_path))

    import services.api_service.collaboration as collaboration

    reloaded = importlib.reload(collaboration)
    reloaded.collaboration_store.add_annotation(
        target_type="alarm",
        target_id="ALERT-1",
        user_id="u-1",
        username="operator1",
        text="check pump alignment",
        tags=["maintenance"],
    )

    reloaded_again = importlib.reload(collaboration)
    annotations = reloaded_again.collaboration_store.list_annotations()

    assert annotations
    assert annotations[0]["text"] == "check pump alignment"


def test_alert_manager_persists_and_recovers_state(tmp_path, monkeypatch):
    state_path = tmp_path / "alert-manager.json"
    monkeypatch.setenv("ALERT_MANAGER_PATH", str(state_path))

    import services.api_service.alert_manager as alert_manager_module

    monkeypatch.setattr(alert_manager_module.notifier, "notify", lambda payload: None)
    monkeypatch.setattr(alert_manager_module.webhook_outbound, "send", lambda payload: None)
    monkeypatch.setattr(alert_manager_module.audit_log, "log", lambda *args, **kwargs: None)

    reloaded = importlib.reload(alert_manager_module)
    monkeypatch.setattr(reloaded.notifier, "notify", lambda payload: None)
    monkeypatch.setattr(reloaded.webhook_outbound, "send", lambda payload: None)
    monkeypatch.setattr(reloaded.audit_log, "log", lambda *args, **kwargs: None)

    alert = reloaded.alert_manager.create_alert(
        asset_id="asset-1",
        tag="Temperature",
        severity="warning",
        message="watch temperature",
    )
    reloaded.alert_manager.acknowledge_alert(alert["alert_id"], user_id="u-1", note="ack")

    reloaded_again = importlib.reload(reloaded)
    monkeypatch.setattr(reloaded_again.notifier, "notify", lambda payload: None)
    monkeypatch.setattr(reloaded_again.webhook_outbound, "send", lambda payload: None)
    monkeypatch.setattr(reloaded_again.audit_log, "log", lambda *args, **kwargs: None)

    loaded = reloaded_again.alert_manager.get_alert(alert["alert_id"])
    assert loaded is not None
    assert loaded["state"] == reloaded_again.AlertState.ACKNOWLEDGED


def test_report_templates_persist_and_recovers_state(tmp_path):
    from services.analytics.reporting import ReportEngine, ReportTemplate

    template_store = tmp_path / "report-templates.json"
    engine = ReportEngine(output_dir=str(tmp_path / "reports"), template_store_path=str(template_store))
    engine.register_template(
        ReportTemplate(
            template_id="custom-report",
            name="Custom Report",
            description="Persistence test",
            query="SELECT 1",
            format="json",
        )
    )

    reloaded = ReportEngine(output_dir=str(tmp_path / "reports"), template_store_path=str(template_store))
    assert any(template["template_id"] == "custom-report" for template in reloaded.list_templates())


def test_report_templates_path_is_honored_from_env(tmp_path, monkeypatch):
    state_path = tmp_path / "report-templates-env.json"
    monkeypatch.setenv("REPORT_TEMPLATE_STORE_PATH", str(state_path))

    import services.analytics.reporting as reporting

    reloaded = importlib.reload(reporting)
    reloaded.report_engine.register_template(
        reloaded.ReportTemplate(
            template_id="env-report",
            name="Env Report",
            description="Env persistence test",
            query="SELECT 1",
            format="json",
        )
    )

    reloaded_again = importlib.reload(reloaded)
    assert any(template["template_id"] == "env-report" for template in reloaded_again.report_engine.list_templates())
