from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

RULES_PATH = Path(__file__).resolve().parents[1] / "docker" / "prometheus" / "alert_rules.yml"
PROM_CONFIG_PATH = Path(__file__).resolve().parents[1] / "docker" / "prometheus" / "prometheus.yml"
COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker" / "docker-compose.yml"

# Metric names the services actually emit (kept in sync with
# services/common/runtime_metrics.py and services/edge_ingest/publisher.py and
# services/historian/client.py).
KNOWN_METRICS = {
    "datastream_broker_consumer_lag_messages",
    "datastream_historian_query_latency_seconds_bucket",
    "datastream_websocket_delivery_lag_seconds_bucket",
    "edge_ingest_dlq_total",
    "edge_ingest_overflow_total",
    "edge_ingest_delivery_failures_total",
    "edge_ingest_reconnects_total",
    "historian_write_total",
}


pytestmark = pytest.mark.skipif(yaml is None, reason="pyyaml not installed")


def _load_rules():
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


def test_rules_file_exists_and_is_valid_yaml():
    assert RULES_PATH.exists(), f"missing {RULES_PATH}"
    data = _load_rules()
    assert "groups" in data
    assert len(data["groups"]) >= 3


def test_every_alert_has_required_fields():
    data = _load_rules()
    for group in data["groups"]:
        for rule in group["rules"]:
            assert "alert" in rule, f"rule missing alert name: {rule}"
            assert "expr" in rule, f"{rule.get('alert')} missing expr"
            assert "for" in rule, f"{rule['alert']} missing 'for' duration"
            assert "labels" in rule and "severity" in rule["labels"], (
                f"{rule['alert']} missing severity label"
            )
            assert "summary" in rule.get("annotations", {}), (
                f"{rule['alert']} missing summary annotation"
            )
            assert rule["labels"]["severity"] in {"warning", "critical"}, (
                f"{rule['alert']} has invalid severity"
            )


def test_alerts_reference_only_known_metrics():
    """Every alert expression references a metric the services actually emit.

    Guards against alert rules that silently never fire because the metric name
    drifted from the instrumentation.
    """
    data = _load_rules()
    for group in data["groups"]:
        for rule in group["rules"]:
            expr = rule["expr"]
            # The expr is a PromQL string; extract bare identifiers that look
            # like metric names (alpha_underscore tokens followed by optional
            # braces/brackets). We assert at least one known metric appears.
            referenced = set()
            # Split on PromQL punctuation so metric names like
            # edge_ingest_dlq_total[5m] are isolated correctly.
            for token in expr.replace("(", " ").replace(")", " ").replace(",", " ").replace("[", " ").replace("]", " ").replace("{", " ").replace("}", " ").replace(">", " ").replace("+", " ").replace("-", " ").replace("*", " ").replace("/", " ").split():
                cleaned = "".join(c for c in token if c.isalnum() or c == "_")
                if cleaned in KNOWN_METRICS:
                    referenced.add(cleaned)
            assert referenced, (
                f"{rule['alert']} expr references no known metric: {expr!r}"
            )


def test_consumer_lag_alerts_cover_warning_and_critical():
    data = _load_rules()
    names = {r["alert"] for g in data["groups"] for r in g["rules"]}
    assert "ConsumerLagHigh" in names
    assert "ConsumerLagCritical" in names


def test_historian_write_failure_alert_exists():
    data = _load_rules()
    names = {r["alert"] for g in data["groups"] for r in g["rules"]}
    assert "HistorianWriteFailures" in names


def test_prometheus_config_loads_rules_file():
    """prometheus.yml must register the alert rules file."""
    cfg = yaml.safe_load(PROM_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "rule_files" in cfg
    assert any("alert_rules.yml" in f for f in cfg["rule_files"]), cfg["rule_files"]


def test_compose_mounts_alert_rules():
    """The prometheus service must mount the alert rules file read-only."""
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    vols = compose["services"]["prometheus"]["volumes"]
    assert any("alert_rules.yml" in v and v.endswith(":ro") for v in vols), vols


def test_default_prometheus_does_not_scrape_optional_python_fallback():
    cfg = yaml.safe_load(PROM_CONFIG_PATH.read_text(encoding="utf-8"))
    jobs = {job["job_name"]: job for job in cfg["scrape_configs"]}
    assert "processor" not in jobs
