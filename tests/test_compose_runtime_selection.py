from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_compose_defaults_to_flink_and_python_is_opt_in():
    compose = yaml.safe_load((ROOT / "docker/docker-compose.yml").read_text(encoding="utf-8"))
    processor = compose["services"]["processor"]
    flink_job = compose["services"]["flink-job"]
    assert "python-fallback" in processor["profiles"]
    assert "profiles" not in flink_job
    assert flink_job["environment"]["RUNTIME_MODE"] == "flink-production"
    assert "FLINK_TASKMANAGER_SLOTS" in compose["services"]["taskmanager"]["environment"]["FLINK_PROPERTIES"]
