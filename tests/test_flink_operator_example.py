from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "k8s" / "flink-operator" / "flinkdeployment.yaml"


def test_flink_operator_example_exists():
    assert EXAMPLE.exists()


def test_flink_operator_example_parses_and_includes_capacity_contract():
    assert yaml is not None, "pyyaml is required for example validation"
    payload = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    assert payload["apiVersion"] == "flink.apache.org/v1beta1"
    assert payload["kind"] == "FlinkDeployment"
    spec = payload["spec"]
    assert spec["image"] == "data-stream/flink-job:latest"
    assert spec["mode"] == "native"
    assert spec["taskManager"]["replicas"] == 3
    assert spec["job"]["parallelism"] == 3
    assert spec["job"]["jarURI"] == "local:///opt/flink/lib/flink-python-1.20.0.jar"
    assert spec["job"]["entryClass"] == "org.apache.flink.client.python.PythonDriver"
    assert spec["job"]["args"] == ["-py", "/opt/stream/services/processor/iot_anomaly_job.py", "-pyfs", "/opt/stream"]
    assert spec["flinkConfiguration"]["pipeline.max-parallelism"] == "120"
    assert spec["flinkConfiguration"]["high-availability"] == "org.apache.flink.kubernetes.highavailability.KubernetesHaServicesFactory"
    assert spec["flinkConfiguration"]["state.checkpoints.dir"].startswith("s3://")
