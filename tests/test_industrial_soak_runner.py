from pathlib import Path

from services.benchmarks.industrial_soak import load_scenario
from services.benchmarks.industrial_soak_runner import _consumer_lag_failures, _metric_total, _scaled_phases, collect_snapshot, run_live


def test_metric_total_sums_labeled_series():
    text = """
industrial_simulator_events_generated_total{protocol=\"mqtt\"} 12
industrial_simulator_events_generated_total{protocol=\"opcua\"} 3
"""
    assert _metric_total(text, "industrial_simulator_events_generated_total") == 15


def test_smoke_schedule_preserves_all_phases():
    scenario = load_scenario("config/benchmarks/industrial-soak.yaml")
    phases = _scaled_phases(scenario, None, True)
    assert sum(phase.duration_seconds for phase in phases) == 30
    assert [phase.name for phase in phases] == [phase.name for phase in scenario.phases]


def test_dry_run_validates_without_starting_docker(tmp_path: Path):
    report = run_live(
        "config/benchmarks/industrial-soak.yaml",
        dry_run=True,
        smoke=True,
        report_dir=tmp_path,
    )
    assert report.passed
    assert report.dry_run
    assert (tmp_path / "industrial-soak.json").exists()
    assert (tmp_path / "industrial-soak.md").exists()


def test_snapshot_exposes_per_service_lag(monkeypatch, tmp_path: Path):
    import services.benchmarks.industrial_soak_runner as runner

    monkeypatch.setattr(runner, "_read_text", lambda url: "")
    monkeypatch.setattr(runner, "_read_json", lambda url: {"status": "ok"})
    monkeypatch.setattr(runner, "_docker_resources", lambda compose_file: (1.0, 100.0))
    monkeypatch.setattr(runner, "_prometheus_scalar", lambda base_url, query: 7.0 if 'service="processor"' in query else 0.0)
    snapshot = collect_snapshot(compose_file=tmp_path / "compose.yml")
    assert snapshot.consumer_lag_by_service["processor"] == 7.0
    assert snapshot.consumer_lag_by_service["fanout"] == 0.0


def test_individual_consumer_backlog_is_a_failure():
    import services.benchmarks.industrial_soak_runner as runner

    snapshot = runner.RuntimeSnapshot(
        "now", 0, 0, 0, 0, 0, 0, 0, True, True, 0, 0, 0,
        {"fanout": 0, "ai_gateway": 10, "ai_enriched_fanout": 0},
    )
    assert _consumer_lag_failures(snapshot, 0) == ["ai_gateway consumer lag exceeded limit: 10 > 0"]


def test_compose_up_preserves_requested_taskmanager_scale(monkeypatch, tmp_path: Path):
    import services.benchmarks.industrial_soak_runner as runner

    captured = {}

    def fake_run(command, check, env):
        captured["command"] = command
        captured["check"] = check
        captured["env"] = env
        return None

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner._compose(tmp_path / "docker-compose.yml", "up", "-d", "--build", env={"A": "B"}, taskmanager_replicas=3)
    assert captured["command"].count("--scale") == 1
    assert "taskmanager=3" in captured["command"]
    assert captured["check"] is True
    assert captured["env"] == {"A": "B"}


def test_compose_up_keeps_scaled_services_in_service_list(monkeypatch, tmp_path: Path):
    import services.benchmarks.industrial_soak_runner as runner

    captured = {}

    def fake_run(command, check, env):
        captured["command"] = command
        return None

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner._compose(tmp_path / "docker-compose.yml", "up", "-d", "--force-recreate", "mqtt-sim", env={}, taskmanager_replicas=3)
    assert "mqtt-sim" in captured["command"]
    assert "taskmanager" in captured["command"]
    assert "flink-job" in captured["command"]
