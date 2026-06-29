"""Tests for TLS configuration in protocol clients and Helm chart."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mqtt_tls_env_vars_present_in_edge_ingest():
    src = (REPO_ROOT / "services" / "edge_ingest" / "main.py").read_text()
    assert "MQTT_CA_CERT" in src
    assert "MQTT_CERTFILE" in src
    assert "MQTT_KEYFILE" in src
    assert "client.tls_set" in src


def test_opcua_tls_env_vars_present_in_edge_ingest():
    src = (REPO_ROOT / "services" / "edge_ingest" / "main.py").read_text()
    assert "OPCUA_CERTIFICATE" in src
    assert "OPCUA_PRIVATE_KEY" in src


def test_modbus_tls_env_vars_present_in_edge_ingest():
    src = (REPO_ROOT / "services" / "edge_ingest" / "main.py").read_text()
    assert "MODBUS_TLS" in src
    assert "MODBUS_CA_CERT" in src
    assert "ssl.create_default_context" in src


def test_helm_values_include_tls_env():
    values = (REPO_ROOT / "k8s" / "helm" / "values.yaml").read_text()
    assert "MQTT_CA_CERT" in values
    assert "OPCUA_CERTIFICATE" in values
    assert "MODBUS_TLS" in values


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
