"""Tests for the Phase 8 control CLI surface."""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.cli import datastreamctl as ctl
from services.datasets.runtime_catalog import (
    DATASET_SOURCES,
    get_dataset_source,
    list_dataset_sources,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_PROFILE = REPO_ROOT / "config" / "site-profiles" / "single-site.yaml"
PROJECT_MANIFEST = REPO_ROOT / "config" / "project-manifest.yaml"


class TestRuntimeCatalog:
    def test_lists_all_sources(self):
        assert len(list_dataset_sources()) == len(DATASET_SOURCES)

    def test_filters_by_category(self):
        synthetic = list_dataset_sources("synthetic")
        assert all(s.category == "synthetic" for s in synthetic)
        assert any(s.dataset_id == "ai4i" for s in synthetic)

    def test_get_known(self):
        assert get_dataset_source("ai4i") is not None
        assert get_dataset_source("ai4i").name.startswith("AI4I")

    def test_get_benchmark_pack(self):
        benchmark = get_dataset_source("industrial-benchmark")
        assert benchmark is not None
        assert benchmark.category == "benchmark"

    def test_get_unknown(self):
        assert get_dataset_source("nope") is None

    def test_mock_is_unlicensed(self):
        assert get_dataset_source("mock").licensed is False


class TestDatastreamctl:
    def _run(self, argv):
        buf = io.StringIO()
        rc = 0
        with redirect_stdout(buf):
            rc = ctl.main(argv)
        return rc, buf.getvalue()

    def test_datasets_command_lists_entries(self):
        rc, out = self._run(["datasets"])
        assert rc == 0
        assert "AI4I" in out
        assert "SWaT" in out

    def test_datasets_category_filter(self):
        rc, out = self._run(["datasets", "--category", "security"])
        assert rc == 0
        assert "SWaT" in out
        assert "WADI" in out
        assert "AI4I" not in out

    def test_scenarios_command_runs(self):
        rc, out = self._run(["scenarios"])
        assert rc == 0
        assert "normal" in out

    def test_doctor_runs_without_network(self):
        rc, _ = self._run(["--api-base", "http://127.0.0.1:9", "--ai-base", "http://127.0.0.1:9", "doctor"])
        assert rc in (0, 2)

    def test_config_command_runs(self):
        rc, out = self._run(["config"])
        assert rc == 0
        assert "DATASTREAM_API_BASE" in out

    def test_site_profile_validate_command_runs(self):
        rc, out = self._run(["site-profile", "validate", str(SITE_PROFILE)])
        assert rc == 0
        assert "valid" in out

    def test_site_profile_show_json_runs(self):
        rc, out = self._run(["site-profile", "show", str(SITE_PROFILE), "--json"])
        assert rc == 0
        assert '"profile_id": "single-site-demo"' in out

    def test_backup_drill_uses_backup_helpers(self, monkeypatch):
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "restore_backup", lambda backup_path, target_database=None: {"status": "success", "database": target_database})
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": False})
        rc, out = self._run(["backup-drill", "--restore-db", "restore_db"])
        assert rc == 0
        assert "backup_status" in out

    def test_release_gate_can_skip_network_and_run_backup(self, monkeypatch):
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "restore_backup", lambda backup_path, target_database=None: {"status": "success", "database": target_database})
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": True})
        rc, out = self._run(["release-gate", str(SITE_PROFILE), "--skip-network"])
        assert rc == 0
        assert "release gate" in out

    def test_project_manifest_show_json_runs(self):
        rc, out = self._run(["project-manifest", "show", str(PROJECT_MANIFEST), "--json"])
        assert rc == 0
        assert '"project_id": "demo-industrial-fleet"' in out

    def test_project_manifest_validate_runs(self):
        rc, out = self._run(["project-manifest", "validate", str(PROJECT_MANIFEST)])
        assert rc == 0
        assert "valid" in out

    def test_project_manifest_sites_runs(self):
        rc, out = self._run(["project-manifest", "sites", str(PROJECT_MANIFEST)])
        assert rc == 0
        assert "demo-site" in out
        assert "plant-a" in out

    def test_project_manifest_bundle_json_runs(self):
        rc, out = self._run(["project-manifest", "bundle", str(PROJECT_MANIFEST), "--site-id", "demo-site", "--json"])
        assert rc == 0
        assert '"DATASTREAM_PROJECT_ID": "demo-industrial-fleet"' in out
        assert '"SITE_ID": "demo-site"' in out

    def test_project_manifest_release_gate_runs(self, monkeypatch):
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "restore_backup", lambda backup_path, target_database=None: {"status": "success", "database": target_database})
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": True})
        rc, out = self._run(["project-manifest", "release-gate", str(PROJECT_MANIFEST), "--skip-network"])
        assert rc == 0
        assert "project release gate" in out

    def test_project_manifest_rollout_acceptance_runs(self, monkeypatch):
        monkeypatch.setattr(
            ctl,
            "_run_release_gate_for_profile",
            lambda profile_path, **kwargs: {
                "profile_id": Path(profile_path).stem,
                "site_id": Path(profile_path).stem,
                "deployment_mode": "single-site",
                "checks": [{"name": "site profile valid", "ok": True, "detail": "ok"}],
                "backup_drill": None,
                "passed": True,
            },
        )
        monkeypatch.setattr(
            ctl,
            "run_site_profile_matrix",
            lambda *args, **kwargs: SimpleNamespace(
                passed=True,
                runs=(
                    SimpleNamespace(
                        site_id="demo-site",
                        deployment_mode="single-site",
                        profile_path=str(SITE_PROFILE),
                        average_events_per_second=5_000.0,
                        passed=True,
                        detail="threshold=1 avg=5000 invalid_events_ok=True",
                    ),
                    SimpleNamespace(
                        site_id="plant-a",
                        deployment_mode="plant-local",
                        profile_path=str(REPO_ROOT / "config" / "site-profiles" / "plant-local.yaml"),
                        average_events_per_second=6_000.0,
                        passed=True,
                        detail="threshold=1 avg=6000 invalid_events_ok=True",
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "project-manifest",
            "rollout-acceptance",
            str(PROJECT_MANIFEST),
            "--skip-network",
            "--skip-backup",
            "--csv",
            str(REPO_ROOT / "data" / "benchmarks" / "industrial_mixed_benchmark.csv"),
            "--site-ids",
            "demo-site,plant-a",
            "--events",
            "12",
            "--batch-size",
            "4",
            "--min-average-events-per-second",
            "1",
        ])
        assert rc == 0
        assert "project rollout acceptance" in out
        assert "demo-site" in out
        assert "plant-a" in out

    def test_project_manifest_export_runs(self, tmp_path):
        rc, out = self._run(["project-manifest", "export", str(PROJECT_MANIFEST), str(tmp_path), "--site-id", "demo-site", "--format", "both"])
        assert rc == 0
        assert (tmp_path / "demo-site.env").exists()
        assert (tmp_path / "demo-site.yaml").exists()
        assert "project export" in out

    def test_project_manifest_lint_runs(self):
        rc, out = self._run(["project-manifest", "lint", str(PROJECT_MANIFEST)])
        assert rc == 0
        assert "project lint" in out

    def test_project_manifest_export_writes_files(self, tmp_path):
        rc, out = self._run(["project-manifest", "export", str(PROJECT_MANIFEST), str(tmp_path), "--site-id", "demo-site", "--format", "both"])
        assert rc == 0
        assert (tmp_path / "demo-site.env").exists()
        assert (tmp_path / "demo-site.yaml").exists()
        assert "project export" in out

    def test_project_manifest_export_systemd_layout(self, tmp_path):
        rc, out = self._run([
            "project-manifest",
            "export",
            str(PROJECT_MANIFEST),
            str(tmp_path),
            "--site-id",
            "demo-site",
            "--format",
            "both",
            "--layout",
            "systemd",
        ])
        assert rc == 0
        assert (tmp_path / "demo-site" / "systemd" / "datastreamd.service").exists()
        assert (tmp_path / "demo-site" / "systemd" / "install.sh").exists()
        assert (tmp_path / "demo-site" / "env" / "site.env").exists()
        assert "systemd" in out

    def test_project_manifest_export_kubernetes_layout(self, tmp_path):
        rc, out = self._run([
            "project-manifest",
            "export",
            str(PROJECT_MANIFEST),
            str(tmp_path),
            "--site-id",
            "plant-a",
            "--format",
            "both",
            "--layout",
            "kubernetes",
        ])
        assert rc == 0
        assert (tmp_path / "plant-a" / "kubernetes" / "deployment.yaml").exists()
        assert (tmp_path / "plant-a" / "kubernetes" / "site-profile-configmap.yaml").exists()
        assert (tmp_path / "plant-a" / "kubernetes" / "kustomization.yaml").exists()
        assert "kubernetes" in out

    def test_project_manifest_package_command(self, tmp_path):
        rc, out = self._run([
            "project-manifest",
            "package",
            str(PROJECT_MANIFEST),
            str(tmp_path),
            "--site-id",
            "demo-site",
            "--format",
            "both",
        ])
        assert rc == 0
        assert (tmp_path / "demo-site" / "flat" / "site.env").exists()
        assert (tmp_path / "demo-site" / "systemd" / "install.sh").exists()
        assert (tmp_path / "demo-site" / "kubernetes" / "helm" / "install.sh").exists()
        assert "project package" in out

    def test_benchmark_deployment_pack_runs(self, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                    "evt-2,opcua,site-a/opcua/pump-2,Pump-2,Vibration,7.5,good,mm/s,Factory-A,Line-1,2026-07-01T00:00:01Z,1,degradation,mock-benchmark,normal,1",
                    "evt-3,modbus,site-a/modbus/pump-3,Pump-3,Pressure,9.1,good,bar,Factory-A,Line-1,2026-07-01T00:00:02Z,1,normal,mock-benchmark,normal,2",
                ]
            ),
            encoding="utf-8",
        )
        rc, out = self._run([
            "benchmark",
            "deployment-pack",
            "--manifest",
            str(PROJECT_MANIFEST),
            "--csv",
            str(csv_path),
            "--site-id",
            "demo-site",
            "--events",
            "24",
            "--batch-size",
            "6",
        ])
        assert rc == 0
        assert "deployment pack benchmark" in out
        assert "export_file_count=" in out

    def test_benchmark_deployment_pack_matrix_runs(self, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                    "evt-2,opcua,site-a/opcua/pump-2,Pump-2,Vibration,7.5,good,mm/s,Factory-A,Line-1,2026-07-01T00:00:01Z,1,degradation,mock-benchmark,normal,1",
                ]
            ),
            encoding="utf-8",
        )
        rc, out = self._run([
            "benchmark",
            "deployment-pack-matrix",
            "--manifest",
            str(PROJECT_MANIFEST),
            "--csv",
            str(csv_path),
            "--site-ids",
            "demo-site,plant-a",
            "--events",
            "12",
            "--batch-size",
            "4",
        ])
        assert rc == 0
        assert "deployment pack benchmark matrix" in out
        assert "demo-site" in out
        assert "plant-a" in out

    def test_benchmark_site_profile_matrix_runs(self, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                    "evt-2,opcua,site-a/opcua/pump-2,Pump-2,Vibration,7.5,good,mm/s,Factory-A,Line-1,2026-07-01T00:00:01Z,1,degradation,mock-benchmark,normal,1",
                ]
            ),
            encoding="utf-8",
        )
        rc, out = self._run([
            "benchmark",
            "site-profile-matrix",
            "--manifest",
            str(PROJECT_MANIFEST),
            "--csv",
            str(csv_path),
            "--site-ids",
            "demo-site,plant-a",
            "--events",
            "12",
            "--batch-size",
            "4",
            "--min-average-events-per-second",
            "1",
        ])
        assert rc == 0
        assert "site profile benchmark matrix" in out
        assert "demo-site" in out
        assert "plant-a" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
