from pathlib import Path

from services.common.preflight import run_preflight


ROOT = Path(__file__).resolve().parents[1]


def test_preflight_reports_missing_files(tmp_path):
    report = run_preflight(
        site_profile=tmp_path / "missing-site.yaml",
        project_manifest=tmp_path / "missing-manifest.yaml",
        soak_scenario=tmp_path / "missing-soak.yaml",
        compose_file=tmp_path / "missing-compose.yaml",
    )
    assert not report.passed
    assert any(not check.passed for check in report.checks)


def test_strict_preflight_can_read_operator_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "POSTGRES_PASSWORD=postgres-production\n"
        "TIMESCALE_PASSWORD=timescale-production\n"
        "MINIO_ROOT_PASSWORD=minio-production\n"
        "GF_SECURITY_ADMIN_PASSWORD=grafana-production\n",
        encoding="utf-8",
    )
    for key in ("POSTGRES_PASSWORD", "TIMESCALE_PASSWORD", "MINIO_ROOT_PASSWORD", "GF_SECURITY_ADMIN_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    report = run_preflight(
        compose_file=ROOT / "docker/docker-compose.yml",
        env_file=env_file,
        strict=True,
    )

    assert report.passed, report.to_dict()
