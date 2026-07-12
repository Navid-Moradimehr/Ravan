from pathlib import Path

from services.benchmarks.industrial_soak import load_scenario
from services.benchmarks.industrial_soak_runner import _metric_total, _scaled_phases, run_live


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
