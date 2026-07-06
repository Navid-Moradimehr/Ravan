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
