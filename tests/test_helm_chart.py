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
    assert "flinkJob:" in content
    assert "edgeIngest:" in content
    assert "secrets:" in content
    assert "existingSecret:" in content
    assert "RUNTIME_MODE:" in content


def test_deployment_template_creates_multiple_deployments():
    content = (HELM_DIR / "templates" / "deployment.yaml").read_text()
    assert "component: api-service" in content
    assert "component: ai-gateway" in content
    assert "component: processor" in content
    assert "component: flink-job" in content
    assert "component: edge-ingest" in content
    assert "secretRef" in content
    assert "runtimeMode" in content or "RUNTIME_MODE" in content


def test_service_template_creates_multiple_services():
    content = (HELM_DIR / "templates" / "service.yaml").read_text()
    assert "component: api-service" in content
    assert "component: ai-gateway" in content
    assert "component: edge-ingest" in content


def test_configmap_template_exists():
    assert (HELM_DIR / "templates" / "configmap.yaml").exists()
    content = (HELM_DIR / "templates" / "configmap.yaml").read_text()
    assert "ConfigMap" in content
    assert "JWT_SECRET" not in content


def test_secret_template_exists():
    assert (HELM_DIR / "templates" / "secret.yaml").exists()
    content = (HELM_DIR / "templates" / "secret.yaml").read_text()
    assert "Secret" in content
    assert "stringData" in content


def test_hpa_template_exists():
    assert (HELM_DIR / "templates" / "hpa.yaml").exists()
    content = (HELM_DIR / "templates" / "hpa.yaml").read_text()
    assert "HorizontalPodAutoscaler" in content
    assert "api-service" in content
    assert "ai-gateway" in content
    assert "processor" in content
    assert "flink-job" in content
    assert "edge-ingest" in content
    assert 'flinkJob.autoscaling.mode "hpa"' in content


def test_helm_values_include_autoscaling():
    values = (HELM_DIR / "values.yaml").read_text()
    assert "autoScaling:" in values
    assert "minReplicas:" in values
    assert "maxReplicas:" in values
    assert "targetCPUUtilizationPercentage:" in values
    assert "mode: operator" in values
    assert "maxParallelism:" in values
    assert "taskmanagerSlots:" in values


def test_helm_values_include_namespace_override():
    values = (HELM_DIR / "values.yaml").read_text()
    assert "namespaceOverride:" in values


def test_profile_overlays_exist():
    profiles_dir = HELM_DIR / "profiles"
    assert (profiles_dir / "single-site-values.yaml").exists()
    assert (profiles_dir / "plant-local-values.yaml").exists()
    assert (profiles_dir / "federated-values.yaml").exists()
    federated = (profiles_dir / "federated-values.yaml").read_text()
    assert "DEPLOYMENT_MODE: \"federated\"" in federated
    assert "RUNTIME_MODE: \"flink-production\"" in federated
    assert "DATASTREAM_CENTRAL_ENDPOINT:" in federated
    plant_local = (profiles_dir / "plant-local-values.yaml").read_text()
    assert "RUNTIME_MODE: \"flink-local\"" in plant_local
    assert "flinkJob:" in plant_local


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
