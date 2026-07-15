from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_flink_job_entrypoint_replaces_owned_job_before_submit() -> None:
    script = (ROOT / "docker" / "flink-job-entrypoint.sh").read_text(encoding="utf-8")
    assert "/jobs/overview" in script
    assert "iot-anomaly-processor" in script
    assert "mode=cancel" in script
    assert "flink run" in script


def test_flink_job_compose_uses_lifecycle_entrypoint() -> None:
    dockerfile = (ROOT / "docker" / "Dockerfile.flink-job").read_text(encoding="utf-8")
    assert "flink-job-entrypoint.sh" in dockerfile
    assert "CMD [\"bash\", \"/opt/stream/flink-job-entrypoint.sh\"]" in dockerfile


def test_flink_runtime_includes_historian_policy_dependency() -> None:
    dockerfile = (ROOT / "docker" / "Dockerfile.flink-runtime").read_text(encoding="utf-8")
    assert "psycopg2-binary" in dockerfile
