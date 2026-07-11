from __future__ import annotations

import json
from pathlib import Path


def test_topic_policy_defaults_to_approved_contract():
    from services.federation.policy import allowed_topics, topic_allowed

    topics = allowed_topics()
    assert topic_allowed("industrial.normalized", topics)
    assert not topic_allowed("industrial.raw", topics)


def test_federation_health_reads_file(tmp_path: Path):
    from services.federation.health import federation_health

    path = tmp_path / "status.json"
    path.write_text(json.dumps({"status": "healthy", "lag": 2}), encoding="utf-8")
    assert federation_health(path) == {"status": "healthy", "lag": 2}


def test_central_bridge_requires_approved_topic(monkeypatch):
    import services.federation.kafka_lakehouse_bridge as bridge

    monkeypatch.setenv("FEDERATION_INPUT_TOPIC", "local.industrial.raw")
    monkeypatch.setenv("FEDERATION_ALLOWED_TOPICS", "industrial.normalized")
    try:
        bridge.main()
    except SystemExit as exc:
        assert "not approved" in str(exc)
