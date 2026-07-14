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


def test_long_running_compose_services_have_restart_and_health_contracts():
    services = _compose()["services"]
    for name in ("kafka", "postgres", "ai-gateway", "api-service", "dashboard", "prometheus"):
        assert services[name].get("restart") == "unless-stopped"
    for name in ("ai-gateway", "api-service", "dashboard"):
        assert "healthcheck" in services[name]


def test_kafka_ui_broker_metrics_are_wired_to_jmx():
    services = _compose()["services"]
    kafka = services["kafka"]
    ui = services["kafka-ui"]

    assert "19097:9997" in kafka["ports"]
    assert kafka["environment"]["KAFKA_JMX_PORT"] == 9997
    jmx_opts = kafka["environment"]["KAFKA_JMX_OPTS"]
    assert "java.rmi.server.hostname=kafka" in jmx_opts
    assert "com.sun.management.jmxremote.rmi.port=9997" in jmx_opts

    assert ui["environment"]["KAFKA_CLUSTERS_0_METRICS_TYPE"] == "JMX"
    assert ui["environment"]["KAFKA_CLUSTERS_0_METRICS_PORT"] == 9997


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
    assert migrate["environment"]["RUN_HISTORIAN_DEDUPE"] == "${RUN_HISTORIAN_DEDUPE:-false}"
    assert "RUN_HISTORIAN_DEDUPE" in command_blob


def test_fanout_and_ai_services_wait_for_timescale_migration():
    services = _compose()["services"]
    for name in ("ai-gateway", "fanout", "processed-fanout", "ai-fanout"):
        depends = services[name].get("depends_on", {})
        assert depends.get("timescaledb-migrate") == {"condition": "service_completed_successfully"}


def test_clean_install_mounts_are_relative_to_compose_directory():
    services = _compose()["services"]
    assert "./postgres/init.sql:/docker-entrypoint-initdb.d/001-init.sql:ro" in services["postgres"]["volumes"]
    assert "./postgres/init-timescale-full.sql:/docker-entrypoint-initdb.d/001-init.sql:ro" in services["timescaledb"]["volumes"]


def test_default_processors_consume_canonical_normalized_topic():
    services = _compose()["services"]
    assert services["processor"]["environment"]["IOT_TOPIC"] == "${IOT_TOPIC:-industrial.normalized}"
    assert services["flink-job"]["environment"]["IOT_TOPIC"] == "${IOT_TOPIC:-industrial.normalized}"


def test_processed_historian_projection_is_independent_of_flink():
    service = _compose()["services"]["processed-fanout"]
    assert service["command"] == ["python", "-m", "services.processor.processed_fanout"]
    assert service["environment"]["PROCESSED_TOPIC"] == "iot.processed"
    assert "18097:8097" in service["ports"]


def test_dashboard_profile_starts_api_service_for_same_origin_proxies():
    services = _compose()["services"]
    assert "ui" in services["api-service"].get("profiles", [])
    depends = services["dashboard"].get("depends_on", {})
    assert depends.get("api-service") == {"condition": "service_healthy"}


def test_soak_metrics_are_exposed_by_processing_workers():
    services = _compose()["services"]
    assert services["processor"]["environment"]["PROCESSOR_METRICS_PORT"] == 8094
    assert services["fanout"]["environment"]["FANOUT_METRICS_PORT"] == 8095
    assert services["ai-fanout"]["environment"]["AI_FANOUT_METRICS_PORT"] == 8096
    for name, host_port in (("processor", "18094:8094"), ("fanout", "18095:8095"), ("ai-fanout", "18096:8096")):
        assert host_port in services[name]["ports"]
