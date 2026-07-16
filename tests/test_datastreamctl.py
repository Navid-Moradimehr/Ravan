"""Tests for the Phase 8 control CLI surface."""
from __future__ import annotations

import io
import json
import importlib
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.cli import datastreamctl as ctl
from services.datasets.runtime_catalog import (
    DATASET_SOURCES,
    DatasetCatalog,
    DatasetSource,
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

    def test_catalog_persists_and_recovers_state(self, tmp_path):
        state_path = tmp_path / "dataset-catalog.json"
        catalog = DatasetCatalog(state_path=state_path)
        catalog.register(
            DatasetSource(
                dataset_id="custom-pack",
                name="Custom Benchmark Pack",
                category="benchmark",
                signals="Synthetic mixed tags for release validation",
                best_use="Regression and smoke testing",
                licensed=False,
            )
        )

        reloaded = DatasetCatalog(state_path=state_path)
        assert reloaded.get_source("custom-pack") is not None
        assert reloaded.get_source("custom-pack").name == "Custom Benchmark Pack"

    def test_catalog_path_is_honored_from_env(self, monkeypatch, tmp_path):
        state_path = tmp_path / "dataset-catalog-env.json"
        monkeypatch.setenv("DATASET_CATALOG_PATH", str(state_path))

        import services.datasets.runtime_catalog as runtime_catalog

        reloaded_module = importlib.reload(runtime_catalog)
        reloaded_module.dataset_catalog.register(
            DatasetSource(
                dataset_id="env-pack",
                name="Env Benchmark Pack",
                category="benchmark",
                signals="Synthetic load for reproducible testing",
                best_use="Benchmarking",
                licensed=False,
            )
        )

        reloaded = DatasetCatalog(state_path=state_path)
        assert reloaded.get_source("env-pack") is not None


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
        assert '"mode": "python-fallback"' in out

    def test_status_reports_site_profile_runtime_mode(self):
        rc, out = self._run(["status", "--site-profile", str(SITE_PROFILE)])
        assert rc == 0
        assert "runtime_mode" in out
        assert "python-fallback" in out

    def test_backup_drill_uses_backup_helpers(self, monkeypatch):
        monkeypatch.setattr(ctl, "collect_historian_snapshot", lambda table_names=None, database=None: {"status": "success", "tables": {"industrial_events": 3}})
        monkeypatch.setattr(ctl, "compare_historian_snapshots", lambda before, after: {"matched": True, "diffs": {}, "before": before, "after": after})
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "reset_database", lambda database, conn: {"status": "success", "database": database})
        monkeypatch.setattr(
            ctl,
            "restore_backup",
            lambda backup_path, target_database=None: {
                "status": "success",
                "database": target_database,
                "hypertables_verified": True,
                "hypertables": {"matched": True},
            },
        )
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": False})
        rc, out = self._run(["backup-drill", "--restore-db", "restore_db"])
        assert rc == 0
        assert "backup_status" in out
        assert "snapshot_match" in out

    def test_backup_drill_writes_report_dir(self, monkeypatch, tmp_path):
        report_dir = tmp_path / "backup-report"
        monkeypatch.setattr(ctl, "collect_historian_snapshot", lambda table_names=None, database=None: {"status": "success", "tables": {"industrial_events": 3}})
        monkeypatch.setattr(ctl, "compare_historian_snapshots", lambda before, after: {"matched": True, "diffs": {}, "before": before, "after": after})
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "reset_database", lambda database, conn: {"status": "success", "database": database})
        monkeypatch.setattr(
            ctl,
            "restore_backup",
            lambda backup_path, target_database=None: {
                "status": "success",
                "database": target_database,
                "hypertables_verified": True,
                "hypertables": {"matched": True},
            },
        )
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": True})
        rc, out = self._run(["backup-drill", "--restore-db", "restore_db", "--report-dir", str(report_dir)])
        assert rc == 0
        assert (report_dir / "backup-drill-summary.json").exists()
        assert (report_dir / "before_snapshot.json").exists()
        assert (report_dir / "backup.json").exists()
        assert (report_dir / "restore_reset.json").exists()
        assert (report_dir / "restore.json").exists()
        assert (report_dir / "after_snapshot.json").exists()
        assert (report_dir / "snapshot_comparison.json").exists()
        assert "report_dir" in out

    def test_backup_drill_matrix_reports_per_site_results(self, monkeypatch, tmp_path):
        report_dir = tmp_path / "backup-report-matrix"
        plant_local_profile = REPO_ROOT / "config" / "site-profiles" / "plant-local.yaml"
        expected_single_site = ctl.load_site_profile(SITE_PROFILE).site.id
        expected_plant_local = ctl.load_site_profile(plant_local_profile).site.id

        def fake_run_backup_drill(backup_dir, tables, restore_db):
            return {
                "before_snapshot": {"status": "success"},
                "backup": {"status": "success", "path": f"{backup_dir}/backup.sql"},
                "backup_elapsed_seconds": 0.1234,
                "restore": {"status": "success", "database": restore_db, "hypertables_verified": True, "hypertables": {"matched": True}},
                "backups": [{"path": f"{backup_dir}/backup.sql"}],
                "wal_g": {"installed": True},
                "after_snapshot": {"status": "success"},
                "snapshot_comparison": {"matched": True, "diffs": {}},
                "restore_elapsed_seconds": 0.2345,
                "total_elapsed_seconds": 0.5678,
            }

        monkeypatch.setattr(ctl, "_run_backup_drill", fake_run_backup_drill)
        rc, out = self._run([
            "backup-drill-matrix",
            "--site-profiles",
            f"{SITE_PROFILE},{plant_local_profile}",
            "--restore-db",
            "restore_db",
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert "backup drill matrix" in out
        assert "passed" in out
        assert expected_single_site in out
        assert expected_plant_local in out
        assert (report_dir / "backup-drill-matrix-summary.json").exists()
        assert (report_dir / f"{expected_single_site}.json").exists()
        assert (report_dir / f"{expected_plant_local}.json").exists()

    def test_local_phase_one_combines_backup_and_benchmark(self, monkeypatch, tmp_path):
        report_dir = tmp_path / "phase-one-report"
        monkeypatch.setattr(
            ctl,
            "_run_backup_drill_matrix",
            lambda *args, **kwargs: {
                "site_profiles": kwargs.get("site_profiles", []),
                "runs": [
                    {
                        "site_profile": str(SITE_PROFILE),
                        "profile_id": "single-site-demo",
                        "site_id": "demo-site",
                        "deployment_mode": "single-site",
                        "backup_dir": "backups/demo-site",
                        "restore_db": "restore_db",
                        "backup_status": "success",
                        "restore_status": "success",
                        "backup_elapsed_seconds": 0.12,
                        "restore_elapsed_seconds": 0.23,
                        "total_elapsed_seconds": 0.45,
                        "snapshot_match": True,
                        "hypertable_match": True,
                        "details": {"backup": {"status": "success"}, "restore": {"status": "success", "hypertables_verified": True}},
                    }
                ],
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
                        average_events_per_second=5000.0,
                        median_events_per_second=5000.0,
                        stdev_events_per_second=0.0,
                        min_events_per_second=5000.0,
                        max_events_per_second=5000.0,
                        repeat_count=1,
                        latency_p99_ms=0.02,
                        passed=True,
                        detail="threshold=1",
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "local-phase-one",
            "--site-profiles",
            str(SITE_PROFILE),
            "--site-ids",
            "demo-site",
            "--events",
            "12",
            "--batch-size",
            "4",
            "--min-average-events-per-second",
            "1",
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert "local phase one" in out
        assert "backup_passed" in out
        assert "benchmark_passed" in out
        assert "acceptance_rows" in out
        assert (report_dir / "local-phase-one-summary.json").exists()
        assert (report_dir / "local-phase-one-acceptance.json").exists()
        assert (report_dir / "backup-drill" / "backup-drill-matrix-summary.json").exists()
        assert (report_dir / "benchmark" / "site-profile-matrix-summary.json").exists()

    def test_local_phase_one_reports_multi_profile_summary(self, monkeypatch, tmp_path):
        report_dir = tmp_path / "phase-one-multi"
        plant_local_profile = REPO_ROOT / "config" / "site-profiles" / "plant-local.yaml"

        monkeypatch.setattr(
            ctl,
            "_run_backup_drill_matrix",
            lambda *args, **kwargs: {
                "site_profiles": kwargs.get("site_profiles", []),
                "runs": [
                    {
                        "site_profile": str(SITE_PROFILE),
                        "profile_id": "single-site-demo",
                        "site_id": "demo-site",
                        "deployment_mode": "single-site",
                        "backup_dir": "backups/demo-site",
                        "restore_db": "restore_db",
                        "backup_status": "success",
                        "restore_status": "success",
                        "backup_elapsed_seconds": 0.12,
                        "restore_elapsed_seconds": 0.23,
                        "total_elapsed_seconds": 0.45,
                        "snapshot_match": True,
                        "hypertable_match": True,
                        "details": {"backup": {"status": "success"}, "restore": {"status": "success", "hypertables_verified": True}},
                        "backup_rto_threshold_seconds": 30.0,
                        "restore_rto_threshold_seconds": 30.0,
                        "rpo_threshold_seconds": 0.0,
                        "rpo_seconds": 0.0,
                        "backup_rto_passed": True,
                        "restore_rto_passed": True,
                        "rpo_passed": True,
                        "accepted": True,
                    },
                    {
                        "site_profile": str(plant_local_profile),
                        "profile_id": "plant-local-demo",
                        "site_id": "plant-a",
                        "deployment_mode": "plant-local",
                        "backup_dir": "backups/plant-a",
                        "restore_db": "restore_db",
                        "backup_status": "success",
                        "restore_status": "success",
                        "backup_elapsed_seconds": 0.18,
                        "restore_elapsed_seconds": 0.34,
                        "total_elapsed_seconds": 0.61,
                        "snapshot_match": True,
                        "hypertable_match": True,
                        "details": {"backup": {"status": "success"}, "restore": {"status": "success", "hypertables_verified": True}},
                        "backup_rto_threshold_seconds": 60.0,
                        "restore_rto_threshold_seconds": 60.0,
                        "rpo_threshold_seconds": 0.0,
                        "rpo_seconds": 0.0,
                        "backup_rto_passed": True,
                        "restore_rto_passed": True,
                        "rpo_passed": True,
                        "accepted": True,
                    },
                ],
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
                        median_events_per_second=5_000.0,
                        stdev_events_per_second=0.0,
                        min_events_per_second=5_000.0,
                        max_events_per_second=5_000.0,
                        repeat_count=1,
                        latency_p99_ms=0.02,
                        passed=True,
                        detail="threshold=1",
                    ),
                    SimpleNamespace(
                        site_id="plant-a",
                        deployment_mode="plant-local",
                        profile_path=str(plant_local_profile),
                        average_events_per_second=6_000.0,
                        median_events_per_second=6_000.0,
                        stdev_events_per_second=0.0,
                        min_events_per_second=6_000.0,
                        max_events_per_second=6_000.0,
                        repeat_count=1,
                        latency_p99_ms=0.03,
                        passed=True,
                        detail="threshold=1",
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "local-phase-one",
            "--site-profiles",
            f"{SITE_PROFILE},{plant_local_profile}",
            "--manifest",
            str(PROJECT_MANIFEST),
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
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert "profile_summaries" in out
        assert "mode=single-site" in out
        assert "mode=plant-local" in out
        payload = json.loads((report_dir / "local-phase-one-summary.json").read_text(encoding="utf-8"))
        assert payload["summary"]["site_profile_count"] == 2
        assert payload["summary"]["passed_site_profiles"] == 2
        assert payload["summary"]["deployment_modes"]["single-site"]["site_profiles"] == 1
        assert payload["summary"]["deployment_modes"]["plant-local"]["site_profiles"] == 1

    def test_local_kubernetes_rehearsal_validates_generated_bundles(self, tmp_path):
        export_dir = tmp_path / "k8s-export"
        report_dir = tmp_path / "k8s-report"
        rc, out = self._run([
            "local-kubernetes-rehearsal",
            "--manifest",
            str(PROJECT_MANIFEST),
            "--site-ids",
            "demo-site",
            "--export-dir",
            str(export_dir),
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert "local kubernetes rehearsal" in out
        assert "kubectl=" in out
        assert (export_dir / "demo-site" / "kubernetes" / "deployment.yaml").exists()
        assert (report_dir / "local-kubernetes-rehearsal-summary.json").exists()

    def test_agent_runtime_contract_and_probe(self, monkeypatch):
        import services.common.agent_runtime as agent_runtime

        captured = []
        monkeypatch.setattr(agent_runtime, "insert_audit_log", lambda event: captured.append(event) or event)

        rc, out = self._run(["agent-runtime", "contract", "--json"])
        assert rc == 0
        assert '"role": "diagnostic_agent_readonly"' in out

        rc, out = self._run([
            "agent-runtime",
            "diagnostic-probe",
            "--actor-id",
            "agent-1",
            "--site-id",
            "demo-site",
            "--tool-name",
            "historian.recent_events",
            "--arguments",
            '{"limit": 5}',
            "--metadata",
            '{"source": "test"}',
            "--json",
        ])
        assert rc == 0
        assert '"tool_name": "historian.recent_events"' in out
        assert '"approved": true' in out
        assert captured and captured[0]["action"] == "agent_tool_call"

    def test_release_gate_can_skip_network_and_run_backup(self, monkeypatch):
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "reset_database", lambda database, conn: {"status": "success", "database": database})
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
        monkeypatch.setattr(ctl, "reset_database", lambda database, conn: {"status": "success", "database": database})
        monkeypatch.setattr(ctl, "restore_backup", lambda backup_path, target_database=None: {"status": "success", "database": target_database})
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": True})
        rc, out = self._run(["project-manifest", "release-gate", str(PROJECT_MANIFEST), "--skip-network"])
        assert rc == 0
        assert "project release gate" in out

    def test_project_manifest_release_gate_writes_report_dir(self, monkeypatch, tmp_path):
        report_dir = tmp_path / "release-gate"
        monkeypatch.setattr(ctl, "create_backup", lambda backup_dir=None, tables=None: {"status": "success", "path": "backups/x.sql"})
        monkeypatch.setattr(ctl, "reset_database", lambda database, conn: {"status": "success", "database": database})
        monkeypatch.setattr(ctl, "restore_backup", lambda backup_path, target_database=None: {"status": "success", "database": target_database})
        monkeypatch.setattr(ctl, "list_backups", lambda backup_dir=None: [{"path": "backups/x.sql"}])
        monkeypatch.setattr(ctl, "get_walg_status", lambda: {"installed": True})
        rc, out = self._run([
            "project-manifest",
            "release-gate",
            str(PROJECT_MANIFEST),
            "--skip-network",
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert (report_dir / "release-gate-summary.json").exists()
        assert (report_dir / "metadata-plane.json").exists()
        assert (report_dir / "governance.json").exists()
        assert "report_dir" in out

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

    def test_project_manifest_rollout_acceptance_writes_report_dir(self, monkeypatch, tmp_path):
        report_dir = tmp_path / "reports"
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
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert (report_dir / "rollout-acceptance-summary.json").exists()
        assert (report_dir / "demo-site.json").exists()
        assert (report_dir / "plant-a.json").exists()
        assert (report_dir / "metadata-plane.json").exists()
        assert (report_dir / "governance.json").exists()
        assert (report_dir / "asset-registry.json").exists()
        assert (report_dir / "event-catalog.json").exists()
        assert (report_dir / "lineage.json").exists()
        assert "report_dir" in out

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

    def test_project_manifest_release_package_command(self, tmp_path):
        rc, out = self._run([
            "project-manifest",
            "release-package",
            str(PROJECT_MANIFEST),
            str(tmp_path),
            "--site-id",
            "demo-site",
            "--format",
            "both",
        ])
        assert rc == 0
        site_root = tmp_path / "demo-site"
        assert (site_root / "release-manifest.json").exists()
        assert (site_root / "checksums.sha256").exists()
        assert (site_root / "README.md").exists()
        assert "project release package" in out

    def test_project_manifest_release_package_signed_command(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATASTREAM_RELEASE_SIGNING_KEY", "test-signing-key")
        rc, out = self._run([
            "project-manifest",
            "release-package",
            str(PROJECT_MANIFEST),
            str(tmp_path),
            "--site-id",
            "demo-site",
            "--format",
            "both",
            "--sign",
        ])
        assert rc == 0
        site_root = tmp_path / "demo-site"
        assert (site_root / "release-signature.json").exists()
        assert "signed" in out

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

    def test_benchmark_site_profile_matrix_writes_report_dir(self, tmp_path):
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
        report_dir = tmp_path / "matrix-report"
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
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert (report_dir / "site-profile-matrix-summary.json").exists()
        assert (report_dir / "demo-site.json").exists()
        assert (report_dir / "plant-a.json").exists()
        assert "report_dir" in out

    def test_benchmark_site_profile_calibration_runs(self, tmp_path):
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
            "site-profile-calibration",
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
        assert "site profile calibration" in out
        assert "recommended_min" in out

    def test_benchmark_site_profile_calibration_writes_report_dir(self, tmp_path):
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
        report_dir = tmp_path / "calibration-report"
        rc, out = self._run([
            "benchmark",
            "site-profile-calibration",
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
            "--report-dir",
            str(report_dir),
        ])
        assert rc == 0
        assert (report_dir / "site-profile-calibration-summary.json").exists()
        assert "report_dir" in out

    def test_benchmark_cgr_gap_report_runs(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            ctl,
            "run_cgr_gap_report",
            lambda *args, **kwargs: SimpleNamespace(
                cgr_target_events_per_second=2_000_000.0,
                cgr_target_p99_ms=80.0,
                documented_full_pipeline_events_per_second=125_830.0,
                documented_full_pipeline_note="reference",
                mixed_replay=SimpleNamespace(
                    csv_path=str(csv_path),
                    events=12,
                    invalid_events=0,
                    batches=3,
                    batch_size=4,
                    elapsed_seconds=0.1,
                    events_per_second=58_548.76,
                    serialized_bytes=512,
                    latency_p99_ms=0.12,
                ),
                cgr_stream_slice=SimpleNamespace(
                    csv_path=str(csv_path),
                    events=12,
                    invalid_events=0,
                    batches=3,
                    batch_size=4,
                    window_limit=25,
                    elapsed_seconds=0.2,
                    events_per_second=58_548.76,
                    serialized_bytes=768,
                    raw_bytes=256,
                    normalized_bytes=256,
                    processed_bytes=256,
                    latency_p99_ms=0.22,
                ),
                flink_runtime_slice=SimpleNamespace(
                    csv_path=str(csv_path),
                    events=12,
                    invalid_events=0,
                    batches=3,
                    batch_size=4,
                    window_limit=25,
                    elapsed_seconds=0.15,
                    events_per_second=72_000.0,
                    serialized_bytes=768,
                    raw_bytes=256,
                    normalized_bytes=256,
                    processed_bytes=256,
                    latency_p99_ms=0.18,
                ),
                real_world_simulator=SimpleNamespace(
                    average_events_per_second=33_242.66,
                    average_latency_p99_ms=0.09,
                    cases=(),
                ),
                site_profile_matrix=SimpleNamespace(
                    passed=True,
                    runs=(),
                ),
                metrics=(
                    SimpleNamespace(
                        label="mixed_replay",
                        observed_events_per_second=58_548.76,
                        target_events_per_second=2_000_000.0,
                        gap_multiplier=34.17,
                        gap_events_per_second=1_941_451.24,
                        gap_percent=97.07,
                        note="current replay path",
                    ),
                ),
                latency_metrics=(
                    SimpleNamespace(
                        label="mixed_replay",
                        observed_p99_ms=0.12,
                        target_p99_ms=80.0,
                        gap_ms=79.88,
                        gap_percent=99.85,
                        note="current replay path",
                    ),
                ),
                latency_note="p99 measured",
            ),
        )
        rc, out = self._run([
            "benchmark",
            "cgr-gap-report",
            "--manifest",
            str(PROJECT_MANIFEST),
            "--csv",
            str(csv_path),
            "--events",
            "12",
            "--batch-size",
            "4",
        ])
        assert rc == 0
        assert "cgr gap report" in out
        assert "mixed_replay" in out
        assert "cgr_stream_slice" in out
        assert "flink_runtime_slice" in out
        assert "gap_x" in out
        assert "latency metric" in out

    def test_benchmark_cgr_stream_slice_runs(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            ctl,
            "run_cgr_stream_slice_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                csv_path=str(csv_path),
                events=12,
                invalid_events=0,
                batches=3,
                batch_size=4,
                window_limit=25,
                elapsed_seconds=0.1,
                events_per_second=120.0,
                serialized_bytes=512,
                raw_bytes=128,
                normalized_bytes=192,
                processed_bytes=192,
                latency_p50_ms=0.01,
                latency_p95_ms=0.02,
                latency_p99_ms=0.03,
                latency_max_ms=0.04,
                stage_breakdown=(
                    SimpleNamespace(
                        name="mapping_validation",
                        operations=12,
                        elapsed_seconds=0.01,
                        events_per_second=1200.0,
                        avg_ms=0.5,
                        latency_p50_ms=0.4,
                        latency_p95_ms=0.6,
                        latency_p99_ms=0.7,
                        latency_max_ms=0.8,
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "benchmark",
            "cgr-stream-slice",
            "--csv",
            str(csv_path),
            "--events",
            "12",
            "--batch-size",
            "4",
        ])
        assert rc == 0
        assert "cgr stream slice benchmark" in out
        assert "events_per_second=" in out
        assert "serialized_bytes=" in out
        assert "mapping_validation" in out

    def test_benchmark_flink_runtime_slice_runs(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            ctl,
            "run_flink_runtime_slice_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                csv_path=str(csv_path),
                events=12,
                invalid_events=0,
                batches=3,
                batch_size=4,
                window_limit=25,
                elapsed_seconds=0.1,
                events_per_second=120.0,
                serialized_bytes=512,
                raw_bytes=128,
                normalized_bytes=192,
                processed_bytes=192,
                latency_p50_ms=0.01,
                latency_p95_ms=0.02,
                latency_p99_ms=0.03,
                latency_max_ms=0.04,
                stage_breakdown=(
                    SimpleNamespace(
                        name="keyed_state_enrichment",
                        operations=12,
                        elapsed_seconds=0.01,
                        events_per_second=1200.0,
                        avg_ms=0.5,
                        latency_p50_ms=0.4,
                        latency_p95_ms=0.6,
                        latency_p99_ms=0.7,
                        latency_max_ms=0.8,
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "benchmark",
            "flink-runtime-slice",
            "--csv",
            str(csv_path),
            "--events",
            "12",
            "--batch-size",
            "4",
        ])
        assert rc == 0
        assert "flink runtime slice benchmark" in out
        assert "events_per_second=" in out
        assert "serialized_bytes=" in out
        assert "keyed_state_enrichment" in out

    def test_benchmark_semantic_graph_slice_runs(self, monkeypatch, tmp_path):
        hierarchy_path = tmp_path / "assets.yaml"
        hierarchy_path.write_text("sites: []", encoding="utf-8")
        monkeypatch.setattr(
            ctl,
            "run_semantic_graph_slice_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                hierarchy_path=str(hierarchy_path),
                iterations=100,
                warmup_iterations=10,
                entity_count=7,
                relationship_count=6,
                measurement_count=9,
                elapsed_seconds=0.01,
                graphs_per_second=10_000.0,
                entities_per_second=70_000.0,
                relationships_per_second=60_000.0,
            ),
        )
        rc, out = self._run([
            "benchmark",
            "semantic-graph-slice",
            "--hierarchy",
            str(hierarchy_path),
            "--iterations",
            "100",
            "--warmup-iterations",
            "10",
        ])
        assert rc == 0
        assert "semantic graph slice benchmark" in out
        assert "graphs_per_second=" in out
        assert "entity_count=7" in out

    def test_benchmark_semantic_graph_query_runs(self, monkeypatch, tmp_path):
        hierarchy_path = tmp_path / "assets.yaml"
        hierarchy_path.write_text("sites: []", encoding="utf-8")
        monkeypatch.setattr(
            ctl,
            "run_semantic_graph_query_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                hierarchy_path=str(hierarchy_path),
                iterations=100,
                warmup_iterations=10,
                query_count=3,
                matched_entities=12,
                matched_relationships=24,
                elapsed_seconds=0.02,
                queries_per_second=15_000.0,
            ),
        )
        rc, out = self._run([
            "benchmark",
            "semantic-graph-query",
            "--hierarchy",
            str(hierarchy_path),
            "--iterations",
            "100",
            "--warmup-iterations",
            "10",
            "--limit",
            "5",
        ])
        assert rc == 0
        assert "semantic graph query benchmark" in out
        assert "queries_per_second=" in out
        assert "query_count=3" in out

    def test_benchmark_semantic_store_write_runs(self, monkeypatch, tmp_path):
        store_path = tmp_path / "semantic-store.json"
        monkeypatch.setattr(
            ctl,
            "run_semantic_store_write_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                store_path=str(store_path),
                iterations=100,
                warmup_iterations=10,
                elapsed_seconds=0.03,
                writes_per_second=10_000.0,
                entity_count=20,
                relationship_count=20,
                lineage_count=20,
            ),
        )
        rc, out = self._run([
            "benchmark",
            "semantic-store-write",
            "--store",
            str(store_path),
            "--iterations",
            "100",
            "--warmup-iterations",
            "10",
        ])
        assert rc == 0
        assert "semantic store write benchmark" in out
        assert "writes_per_second=" in out
        assert "lineage_count=20" in out

    def test_benchmark_metadata_plane_snapshot_runs(self, monkeypatch, tmp_path):
        asset_config = tmp_path / "assets.yaml"
        asset_config.write_text("sites: []", encoding="utf-8")
        project_manifest = tmp_path / "project.yaml"
        project_manifest.write_text("schema_version: 1\nproject_id: demo\nname: demo\nsites: []\n", encoding="utf-8")
        monkeypatch.setattr(
            ctl,
            "run_metadata_artifacts_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                iterations=100,
                warmup_iterations=10,
                elapsed_seconds=0.01,
                snapshots_per_second=10_000.0,
                bundle_counts={"metadata_plane_assets": 1, "metadata_plane_topics": 6, "schema_count": 3},
            ),
        )
        rc, out = self._run([
            "benchmark",
            "metadata-plane-snapshot",
            "--iterations",
            "100",
            "--warmup-iterations",
            "10",
            "--asset-config",
            str(asset_config),
            "--project-manifest",
            str(project_manifest),
        ])
        assert rc == 0
        assert "metadata plane snapshot benchmark" in out
        assert "snapshots_per_second=" in out

    def test_benchmark_end_to_end_pipeline_runs(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            ctl,
            "run_end_to_end_pipeline_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                csv_path=str(csv_path),
                wire_format="msgpack",
                events=12,
                invalid_events=0,
                batches=3,
                batch_size=4,
                window_limit=25,
                elapsed_seconds=0.1,
                events_per_second=120.0,
                payload_bytes=512,
                roundtrip_bytes=512,
                latency_p50_ms=0.01,
                latency_p95_ms=0.02,
                latency_p99_ms=0.03,
                latency_max_ms=0.04,
                stage_breakdown=(
                    SimpleNamespace(
                        name="wire_roundtrip",
                        operations=12,
                        elapsed_seconds=0.01,
                        events_per_second=1200.0,
                        avg_ms=0.5,
                        latency_p50_ms=0.4,
                        latency_p95_ms=0.6,
                        latency_p99_ms=0.7,
                        latency_max_ms=0.8,
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "benchmark",
            "end-to-end-pipeline",
            "--csv",
            str(csv_path),
            "--events",
            "12",
            "--batch-size",
            "4",
            "--wire-format",
            "msgpack",
        ])
        assert rc == 0
        assert "end to end pipeline benchmark" in out
        assert "wire_format=" in out
        assert "wire_roundtrip" in out

    def test_benchmark_production_pipeline_runs(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            ctl,
            "run_production_pipeline_benchmark",
            lambda *args, **kwargs: SimpleNamespace(
                csv_path=str(csv_path),
                runtime_mode="flink-production",
                execution_path="flink_runtime_slice",
                events=12,
                invalid_events=0,
                batches=3,
                batch_size=4,
                window_limit=25,
                elapsed_seconds=0.1,
                events_per_second=120.0,
                serialized_bytes=512,
                roundtrip_bytes=512,
                latency_p50_ms=0.01,
                latency_p95_ms=0.02,
                latency_p99_ms=0.03,
                latency_max_ms=0.04,
                stage_breakdown=(
                    SimpleNamespace(
                        name="keyed_state_enrichment",
                        operations=12,
                        elapsed_seconds=0.01,
                        events_per_second=1200.0,
                        avg_ms=0.5,
                        latency_p50_ms=0.4,
                        latency_p95_ms=0.6,
                        latency_p99_ms=0.7,
                        latency_max_ms=0.8,
                    ),
                ),
            ),
        )
        rc, out = self._run([
            "benchmark",
            "production-pipeline",
            "--csv",
            str(csv_path),
            "--events",
            "12",
            "--batch-size",
            "4",
            "--runtime-mode",
            "flink-production",
        ])
        assert rc == 0
        assert "production pipeline benchmark" in out
        assert "runtime_mode=flink-production" in out
        assert "execution_path=flink_runtime_slice" in out

    def test_benchmark_session_repeatability_compares_against_baseline(self, monkeypatch, tmp_path):
        csv_path = tmp_path / "mock.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                    "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                ]
            ),
            encoding="utf-8",
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "runtime_mode": "python-fallback",
                    "median_events_per_second": 100.0,
                    "median_latency_p99_ms": 1.5,
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            ctl,
            "run_production_pipeline_repeatability",
            lambda *args, **kwargs: SimpleNamespace(
                csv_path=str(csv_path),
                runtime_mode="python-fallback",
                wire_format="json",
                repeat_count=3,
                runs=(
                    SimpleNamespace(
                        runtime_mode="python-fallback",
                        execution_path="end_to_end_pipeline",
                        events_per_second=110.0,
                        latency_p99_ms=1.1,
                        invalid_events=0,
                    ),
                    SimpleNamespace(
                        runtime_mode="python-fallback",
                        execution_path="end_to_end_pipeline",
                        events_per_second=120.0,
                        latency_p99_ms=1.0,
                        invalid_events=0,
                    ),
                    SimpleNamespace(
                        runtime_mode="python-fallback",
                        execution_path="end_to_end_pipeline",
                        events_per_second=115.0,
                        latency_p99_ms=1.2,
                        invalid_events=0,
                    ),
                ),
                average_events_per_second=115.0,
                median_events_per_second=115.0,
                stdev_events_per_second=4.08,
                min_events_per_second=110.0,
                max_events_per_second=120.0,
                average_latency_p99_ms=1.1,
                median_latency_p99_ms=1.1,
                stdev_latency_p99_ms=0.08,
                min_latency_p99_ms=1.0,
                max_latency_p99_ms=1.2,
                baseline_label="baseline",
                baseline_events_per_second=100.0,
                baseline_latency_p99_ms=1.5,
                delta_events_per_second=15.0,
                delta_events_percent=15.0,
                delta_latency_p99_ms=-0.4,
                delta_latency_percent=-26.67,
            ),
        )
        rc, out = self._run([
            "benchmark",
            "session-repeatability",
            "--csv",
            str(csv_path),
            "--events",
            "12",
            "--batch-size",
            "4",
            "--repeat-count",
            "3",
            "--baseline-report",
            str(baseline_path),
        ])
        assert rc == 0
        assert "production pipeline session repeatability" in out
        assert "delta_events_percent=15.0" in out
        assert "median_events_per_second=115.0" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
