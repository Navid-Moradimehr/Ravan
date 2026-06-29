"""Basic structural validation of the Helm chart."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HELM_DIR = REPO_ROOT / "k8s" / "helm"


def test_chart_yaml_exists():
    assert (HELM_DIR / "Chart.yaml").exists()


def test_values_yaml_has_service_toggles():
    content = (HELM_DIR / "values.yaml").read_text()
    assert "apiService:" in content
    assert "aiGateway:" in content
    assert "processor:" in content
    assert "edgeIngest:" in content
    assert "JWT_SECRET" in content


def test_deployment_template_creates_multiple_deployments():
    content = (HELM_DIR / "templates" / "deployment.yaml").read_text()
    assert "component: api-service" in content
    assert "component: ai-gateway" in content
    assert "component: processor" in content
    assert "component: edge-ingest" in content


def test_service_template_creates_multiple_services():
    content = (HELM_DIR / "templates" / "service.yaml").read_text()
    assert "component: api-service" in content
    assert "component: ai-gateway" in content
    assert "component: edge-ingest" in content


def test_configmap_template_exists():
    assert (HELM_DIR / "templates" / "configmap.yaml").exists()
    content = (HELM_DIR / "templates" / "configmap.yaml").read_text()
    assert "ConfigMap" in content


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
