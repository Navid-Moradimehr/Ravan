from services.common.ai_reporting import AIReportingPolicy, SustainedAnomalyTracker


def event(severity="warning"):
    return {"site_id": "plant-a", "asset_id": "pump-1", "tag": "vibration", "severity": severity, "value": 9.2}


def test_tracker_emits_once_after_sustained_warning_and_rearms():
    policy = AIReportingPolicy(anomaly_enabled=True, anomaly_severity="warning", anomaly_duration_seconds=20, anomaly_min_samples=3, anomaly_rearm_seconds=5, anomaly_cooldown_seconds=60)
    tracker = SustainedAnomalyTracker()
    assert tracker.update(event(), policy, now=0) is None
    assert tracker.update(event(), policy, now=10) is None
    evidence = tracker.update(event(), policy, now=20)
    assert evidence and len(evidence) == 3
    assert tracker.update(event(), policy, now=30) is None
    tracker.update(event("normal"), policy, now=31)
    tracker.update(event("normal"), policy, now=37)
    assert tracker.update(event(), policy, now=60) is None


def test_tracker_excludes_replay_events():
    policy = AIReportingPolicy(anomaly_enabled=True, anomaly_severity="warning")
    tracker = SustainedAnomalyTracker()
    assert tracker.update({**event(), "replay_source": "dataset"}, policy, now=100) is None


def test_tracker_emits_recovery_transition_after_rearm():
    policy = AIReportingPolicy(anomaly_enabled=True, anomaly_severity="warning", anomaly_duration_seconds=20, anomaly_min_samples=3, anomaly_rearm_seconds=5)
    tracker = SustainedAnomalyTracker()
    tracker.update_transition(event(), policy, now=0)
    tracker.update_transition(event(), policy, now=10)
    anomaly = tracker.update_transition(event(), policy, now=20)
    assert anomaly and anomaly["kind"] == "anomaly"
    assert tracker.update_transition(event("normal"), policy, now=21) is None
    recovery = tracker.update_transition(event("normal"), policy, now=26)
    assert recovery and recovery["kind"] == "recovery"
