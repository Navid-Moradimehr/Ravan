from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REPO = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPO / "docker" / "docker-compose.yml"

pytestmark = pytest.mark.skipif(yaml is None, reason="pyyaml not installed")

CANONICAL_TOPICS = {
    "industrial.raw",
    "industrial.normalized",
    "industrial.dlq",
    "iot.raw",
    "iot.processed",
    "iot.ai_enriched",
}


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_kafka_init_service_exists():
    services = _compose()["services"]
    assert "kafka-init" in services


def test_kafka_init_depends_on_healthy_kafka():
    init = _compose()["services"]["kafka-init"]
    depends = init.get("depends_on", {})
    assert depends.get("kafka") == {"condition": "service_healthy"}


def test_kafka_init_creates_all_canonical_topics():
    init = _compose()["services"]["kafka-init"]
    command_blob = ""
    cmd = init["command"]
    if isinstance(cmd, list):
        command_blob = " ".join(cmd)
    else:
        command_blob = str(cmd)
    for topic in CANONICAL_TOPICS:
        assert topic in command_blob, f"kafka-init missing topic creation: {topic}"


def test_kafka_init_uses_if_not_exists():
    init = _compose()["services"]["kafka-init"]
    cmd = init["command"]
    command_blob = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    assert "--create" in command_blob
    assert "--if-not-exists" in command_blob


def test_kafka_init_is_one_shot():
    init = _compose()["services"]["kafka-init"]
    assert init.get("restart") == "no"
    assert init.get("image") == "apache/kafka:4.1.2"


def test_timescaledb_migrate_service_exists_and_is_one_shot():
    services = _compose()["services"]
    assert "timescaledb-migrate" in services
    migrate = services["timescaledb-migrate"]
    assert migrate.get("restart") == "no"
    assert migrate.get("depends_on", {}).get("timescaledb") == {"condition": "service_healthy"}


def test_timescaledb_migrate_repairs_historian_uniqueness():
    migrate = _compose()["services"]["timescaledb-migrate"]
    command_blob = " ".join(migrate.get("command", [])) if isinstance(migrate.get("command"), list) else str(migrate.get("command"))
    assert "timescaledb.max_tuples_decompressed_per_dml_transaction = 0" in command_blob
    assert "DELETE FROM industrial_events" in command_blob
    assert "DELETE FROM processed_events" in command_blob
    assert "DELETE FROM dead_letter_events" in command_blob
    assert "industrial_events_event_id_uniq" in command_blob
    assert "processed_events_event_id_uniq" in command_blob
    assert "dead_letter_events_event_id_uniq" in command_blob


def test_fanout_and_ai_services_wait_for_timescale_migration():
    services = _compose()["services"]
    for name in ("ai-gateway", "fanout", "ai-fanout"):
        depends = services[name].get("depends_on", {})
        assert depends.get("timescaledb-migrate") == {"condition": "service_completed_successfully"}


def test_dashboard_profile_starts_api_service_for_same_origin_proxies():
    services = _compose()["services"]
    assert "ui" in services["api-service"].get("profiles", [])
    depends = services["dashboard"].get("depends_on", {})
    assert depends.get("api-service") == {"condition": "service_started"}
