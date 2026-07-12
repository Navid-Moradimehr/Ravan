from pathlib import Path

from services.common.preflight import run_preflight


ROOT = Path(__file__).resolve().parents[1]


def test_repository_preflight_passes():
    report = run_preflight(
        site_profile=ROOT / "config/site-profiles/single-site.yaml",
        project_manifest=ROOT / "config/project-manifest.yaml",
        soak_scenario=ROOT / "config/benchmarks/industrial-soak.yaml",
        compose_file=ROOT / "docker/docker-compose.yml",
    )
    assert report.passed, report.to_dict()


def test_preflight_reports_missing_files(tmp_path):
    report = run_preflight(
        site_profile=tmp_path / "missing-site.yaml",
        project_manifest=tmp_path / "missing-manifest.yaml",
        soak_scenario=tmp_path / "missing-soak.yaml",
        compose_file=tmp_path / "missing-compose.yaml",
    )
    assert not report.passed
    assert any(not check.passed for check in report.checks)
