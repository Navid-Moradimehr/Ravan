"""datastreamctl - admin/control CLI for Local Stream Engine.

Part of the Phase 8 distribution surface. Talks to the already-running
services (api_service on 8020, ai_gateway on 8080) and surfaces config,
health, scenario, and dataset information so operators can run the
platform from one command without a browser.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import platform
import shutil
import subprocess
import time
import sys
import tempfile
import ast
from typing import Any
from pathlib import Path

import yaml

from services.common.project_manifest import load_project_manifest, validate_project_manifest
from services.common.site_profiles import load_site_profile, validate_site_profile
from services.common.agent_runtime import build_agent_runtime_contract
from services.benchmarks.deployment_pack import format_result as format_deployment_pack_result
from services.benchmarks.deployment_pack import format_matrix_result as format_deployment_pack_matrix_result
from services.benchmarks.deployment_pack import run_benchmark as run_deployment_pack_benchmark
from services.benchmarks.deployment_pack import run_matrix as run_deployment_pack_matrix
from services.benchmarks.cgr_gap import format_result as format_cgr_gap_result
from services.benchmarks.cgr_gap import run_report as run_cgr_gap_report
from services.benchmarks.cgr_stream_slice import format_result as format_cgr_stream_slice_result
from services.benchmarks.cgr_stream_slice import run_benchmark as run_cgr_stream_slice_benchmark
from services.benchmarks.end_to_end_pipeline import format_result as format_end_to_end_pipeline_result
from services.benchmarks.end_to_end_pipeline import run_benchmark as run_end_to_end_pipeline_benchmark
from services.benchmarks.flink_runtime_slice import format_result as format_flink_runtime_slice_result
from services.benchmarks.flink_runtime_slice import run_benchmark as run_flink_runtime_slice_benchmark
from services.benchmarks.production_pipeline import format_result as format_production_pipeline_result
from services.benchmarks.production_pipeline import run_benchmark as run_production_pipeline_benchmark
from services.benchmarks.real_world_simulator import format_result as format_real_world_simulator_result
from services.benchmarks.real_world_simulator import run_suite as run_real_world_simulator_suite
from services.benchmarks.semantic_graph_slice import format_result as format_semantic_graph_slice_result
from services.benchmarks.semantic_graph_slice import run_benchmark as run_semantic_graph_slice_benchmark
from services.benchmarks.semantic_graph_query import format_result as format_semantic_graph_query_result
from services.benchmarks.semantic_graph_query import run_benchmark as run_semantic_graph_query_benchmark
from services.benchmarks.semantic_store_write import format_result as format_semantic_store_write_result
from services.benchmarks.semantic_store_write import run_benchmark as run_semantic_store_write_benchmark
from services.benchmarks.site_profile_calibration import format_result as format_site_profile_calibration_result
from services.benchmarks.site_profile_calibration import run_calibration as run_site_profile_calibration
from services.benchmarks.site_profile_matrix import format_result as format_site_profile_matrix_result
from services.benchmarks.site_profile_matrix import run_matrix as run_site_profile_matrix
from services.historian.backup import (
    collect_historian_snapshot,
    compare_historian_snapshots,
    create_backup,
    get_walg_status,
    list_backups,
    restore_backup,
)

DEFAULT_API_BASE = os.getenv("DATASTREAM_API_BASE", "http://localhost:8020")
DEFAULT_AI_BASE = os.getenv("DATASTREAM_AI_BASE", "http://localhost:8080")


def _import_lazily(module_name: str):
    try:
        return __import__(module_name)
    except Exception:
        return None


def _load_runtime_catalog():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from services.datasets.runtime_catalog import list_dataset_sources

        return list_dataset_sources()
    except Exception:
        return []


def _load_scenario_catalog():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from services.scenarios.engine import list_scenarios

        return list_scenarios()
    except Exception:
        return []


def _http_get(url: str, timeout: float = 2.0) -> tuple[int, Any]:
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return 0, {"error": str(exc)}


def _print_row(label: str, value: Any) -> None:
    print(f"{label:<22}{value}")


def _host_profile() -> dict[str, Any]:
    memory_gb = None
    try:
        import psutil  # type: ignore

        memory_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        memory_gb = None
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "memory_gb": memory_gb,
    }


def _parse_tables(value: str | None) -> list[str] | None:
    if not value:
        return None
    tables = [part.strip() for part in value.split(",") if part.strip()]
    return tables or None


def _restore_threshold_seconds(deployment_mode: str) -> float:
    if deployment_mode == "single-site":
        return 30.0
    if deployment_mode == "plant-local":
        return 60.0
    if deployment_mode == "federated":
        return 120.0
    return 45.0


def _run_backup_drill(backup_dir: str | None, tables: list[str] | None, restore_db: str | None) -> dict[str, Any]:
    started_at = time.perf_counter()
    before_snapshot = collect_historian_snapshot()
    backup_started_at = time.perf_counter()
    backup_result = create_backup(backup_dir=backup_dir, tables=tables)
    backup_elapsed_seconds = round(time.perf_counter() - backup_started_at, 4)
    result: dict[str, Any] = {
        "before_snapshot": before_snapshot,
        "backup": backup_result,
        "backup_elapsed_seconds": backup_elapsed_seconds,
        "restore": None,
        "backups": list_backups(backup_dir=backup_dir),
        "wal_g": get_walg_status(),
        "after_snapshot": None,
        "snapshot_comparison": None,
        "restore_elapsed_seconds": None,
        "total_elapsed_seconds": None,
    }
    if result["backup"].get("status") != "success":
        result["total_elapsed_seconds"] = round(time.perf_counter() - started_at, 4)
        return result
    if restore_db:
        restore_started_at = time.perf_counter()
        result["restore"] = restore_backup(result["backup"]["path"], restore_db)
        result["restore_elapsed_seconds"] = round(time.perf_counter() - restore_started_at, 4)
        if result["restore"].get("status") == "success":
            after_snapshot = collect_historian_snapshot()
            result["after_snapshot"] = after_snapshot
            result["snapshot_comparison"] = compare_historian_snapshots(before_snapshot, after_snapshot)
    result["total_elapsed_seconds"] = round(time.perf_counter() - started_at, 4)
    return result


def _run_backup_drill_matrix(
    site_profiles: list[str],
    *,
    backup_dir: str | None,
    tables: list[str] | None,
    restore_db: str | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for site_profile in site_profiles:
        profile = load_site_profile(site_profile)
        profile_backup_dir = backup_dir or profile.backups.directory
        profile_restore_db = restore_db or profile.backups.restore_test_database
        restore_threshold_seconds = _restore_threshold_seconds(profile.deployment_mode)
        backup_threshold_seconds = max(restore_threshold_seconds / 2.0, 10.0)
        drill = _run_backup_drill(profile_backup_dir, tables, profile_restore_db)
        backup_elapsed_seconds = float(drill.get("backup_elapsed_seconds") or 0.0)
        restore_elapsed_seconds = float(drill.get("restore_elapsed_seconds") or 0.0)
        snapshot_match = bool(drill.get("snapshot_comparison") and drill["snapshot_comparison"].get("matched"))
        backup_rto_passed = backup_elapsed_seconds <= backup_threshold_seconds
        restore_rto_passed = restore_elapsed_seconds <= restore_threshold_seconds if drill["restore"] else False
        rpo_seconds = 0.0 if snapshot_match else 1.0
        rpo_threshold_seconds = 0.0
        rpo_passed = snapshot_match and rpo_seconds <= rpo_threshold_seconds
        accepted = bool(
            drill["backup"].get("status") == "success"
            and (drill["restore"] is None or drill["restore"].get("status") == "success")
            and snapshot_match
            and backup_rto_passed
            and (drill["restore"] is None or restore_rto_passed)
            and rpo_passed
        )
        rows.append(
            {
                "site_profile": site_profile,
                "profile_id": profile.profile_id,
                "site_id": profile.site.id,
                "deployment_mode": profile.deployment_mode,
                "backup_dir": profile_backup_dir,
                "restore_db": profile_restore_db,
                "backup_status": drill["backup"].get("status", "unknown"),
                "restore_status": drill["restore"].get("status", "skipped") if drill["restore"] else "skipped",
                "backup_elapsed_seconds": backup_elapsed_seconds,
                "restore_elapsed_seconds": restore_elapsed_seconds,
                "total_elapsed_seconds": drill.get("total_elapsed_seconds", 0.0),
                "snapshot_match": snapshot_match,
                "backup_rto_threshold_seconds": backup_threshold_seconds,
                "restore_rto_threshold_seconds": restore_threshold_seconds,
                "rpo_threshold_seconds": rpo_threshold_seconds,
                "rpo_seconds": rpo_seconds,
                "backup_rto_passed": backup_rto_passed,
                "restore_rto_passed": restore_rto_passed,
                "rpo_passed": rpo_passed,
                "accepted": accepted,
                "details": drill,
            }
        )
    passed = all(
        row["accepted"]
        for row in rows
    )
    return {
        "site_profiles": site_profiles,
        "runs": rows,
        "passed": passed,
    }


def _write_backup_drill_report(report_dir: str, payload: dict[str, Any]) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    summary_path = output_dir / "backup-drill-summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written.append(summary_path)
    for key in ("before_snapshot", "backup", "restore", "after_snapshot", "snapshot_comparison", "wal_g"):
        if payload.get(key) is None:
            continue
        item_path = output_dir / f"{key}.json"
        item_path.write_text(json.dumps(payload[key], indent=2), encoding="utf-8")
        written.append(item_path)
    return written


def _write_backup_drill_matrix_report(report_dir: str, payload: dict[str, Any]) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    summary_path = output_dir / "backup-drill-matrix-summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written.append(summary_path)
    for run in payload.get("runs", []):
        run_path = output_dir / f"{run['site_id']}.json"
        run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
        written.append(run_path)
    return written


def _write_local_phase_one_report(report_dir: str, payload: dict[str, Any]) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "local-phase-one-summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written: list[Path] = [summary_path]

    acceptance_path = output_dir / "local-phase-one-acceptance.json"
    acceptance_path.write_text(json.dumps(payload.get("acceptance", []), indent=2), encoding="utf-8")
    written.append(acceptance_path)

    backup_payload = payload.get("backup_drill")
    if isinstance(backup_payload, dict):
        backup_dir = output_dir / "backup-drill"
        written.extend(_write_backup_drill_matrix_report(str(backup_dir), backup_payload))

    benchmark_payload = payload.get("benchmark")
    if isinstance(benchmark_payload, dict):
        benchmark_dir = output_dir / "benchmark"
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        benchmark_summary = benchmark_dir / "site-profile-matrix-summary.json"
        benchmark_summary.write_text(json.dumps(benchmark_payload, indent=2), encoding="utf-8")
        written.append(benchmark_summary)
        for run in benchmark_payload.get("runs", []):
            run_path = benchmark_dir / f"{run['site_id']}.json"
            run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
            written.append(run_path)
    return written


def _write_local_kubernetes_rehearsal_report(report_dir: str, payload: dict[str, Any]) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    summary_path = output_dir / "local-kubernetes-rehearsal-summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written.append(summary_path)
    for run in payload.get("runs", []):
        run_path = output_dir / f"{run['site_id']}.json"
        run_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
        written.append(run_path)
    return written


def _serialize_site_profile_matrix_result(result: Any) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "runs": [
            {
                "site_id": run.site_id,
                "deployment_mode": run.deployment_mode,
                "profile_path": run.profile_path,
                "average_events_per_second": run.average_events_per_second,
                "median_events_per_second": run.median_events_per_second,
                "stdev_events_per_second": run.stdev_events_per_second,
                "min_events_per_second": run.min_events_per_second,
                "max_events_per_second": run.max_events_per_second,
                "repeat_count": run.repeat_count,
                "latency_p99_ms": run.latency_p99_ms,
                "passed": run.passed,
                "detail": run.detail,
            }
            for run in result.runs
        ],
    }


def _serialize_local_phase_one_acceptance(backup_result: dict[str, Any], benchmark_result: Any) -> list[dict[str, Any]]:
    benchmark_runs = {run.site_id: run for run in benchmark_result.runs}
    acceptance: list[dict[str, Any]] = []
    for backup_run in backup_result["runs"]:
        benchmark_run = benchmark_runs.get(backup_run["site_id"])
        benchmark_passed = bool(benchmark_run.passed) if benchmark_run else False
        benchmark_threshold = float(benchmark_run.detail.split("threshold=")[1].split()[0]) if benchmark_run and "threshold=" in benchmark_run.detail else None
        backup_rto_threshold_seconds = float(backup_run.get("backup_rto_threshold_seconds", 30.0))
        restore_rto_threshold_seconds = float(backup_run.get("restore_rto_threshold_seconds", 60.0))
        rpo_threshold_seconds = float(backup_run.get("rpo_threshold_seconds", 0.0))
        backup_rto_passed = bool(backup_run.get("backup_rto_passed", backup_run["backup_elapsed_seconds"] <= backup_rto_threshold_seconds))
        restore_rto_passed = bool(backup_run.get("restore_rto_passed", backup_run["restore_elapsed_seconds"] <= restore_rto_threshold_seconds))
        rpo_passed = bool(backup_run.get("rpo_passed", backup_run.get("snapshot_match", False) and backup_run.get("rpo_seconds", 0.0) <= rpo_threshold_seconds))
        accepted = bool(backup_run.get(
            "accepted",
            backup_rto_passed and restore_rto_passed and rpo_passed and backup_run.get("backup_status") == "success" and backup_run.get("restore_status") in {"success", "skipped"},
        ))
        acceptance.append(
            {
                "site_id": backup_run["site_id"],
                "profile_id": backup_run["profile_id"],
                "deployment_mode": backup_run["deployment_mode"],
                "backup_rto_seconds": backup_run["backup_elapsed_seconds"],
                "backup_rto_threshold_seconds": backup_rto_threshold_seconds,
                "backup_rto_passed": backup_rto_passed,
                "restore_rto_seconds": backup_run["restore_elapsed_seconds"],
                "restore_rto_threshold_seconds": restore_rto_threshold_seconds,
                "restore_rto_passed": restore_rto_passed,
                "rpo_seconds": backup_run.get("rpo_seconds", 0.0),
                "rpo_threshold_seconds": rpo_threshold_seconds,
                "rpo_passed": rpo_passed,
                "benchmark_average_events_per_second": benchmark_run.average_events_per_second if benchmark_run else None,
                "benchmark_threshold_events_per_second": benchmark_threshold,
                "benchmark_passed": benchmark_passed,
                "passed": bool(accepted and benchmark_passed),
            }
        )
    return acceptance


def _summarize_local_phase_one_acceptance(acceptance: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "site_profile_count": len(acceptance),
        "passed_site_profiles": sum(1 for row in acceptance if row["passed"]),
        "failed_site_profiles": sum(1 for row in acceptance if not row["passed"]),
        "deployment_modes": {},
    }
    deployment_modes: dict[str, dict[str, Any]] = {}
    for row in acceptance:
        mode = row["deployment_mode"]
        bucket = deployment_modes.setdefault(
            mode,
            {
                "site_profiles": 0,
                "passed_site_profiles": 0,
                "failed_site_profiles": 0,
                "site_ids": [],
            },
        )
        bucket["site_profiles"] += 1
        bucket["site_ids"].append(row["site_id"])
        if row["passed"]:
            bucket["passed_site_profiles"] += 1
        else:
            bucket["failed_site_profiles"] += 1
    summary["deployment_modes"] = {
        mode: {
            "site_profiles": bucket["site_profiles"],
            "passed_site_profiles": bucket["passed_site_profiles"],
            "failed_site_profiles": bucket["failed_site_profiles"],
            "site_ids": sorted(bucket["site_ids"]),
        }
        for mode, bucket in sorted(deployment_modes.items())
    }
    return summary


def _validate_yaml_documents(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
        docs = [doc for doc in yaml.safe_load_all(raw_text) if doc is not None]
    except Exception as exc:
        return {
            "path": str(path),
            "valid": False,
            "document_count": 0,
            "kinds": [],
            "error": str(exc),
        }

    kinds = []
    for doc in docs:
        if isinstance(doc, dict):
            kinds.append(str(doc.get("kind", "")))
    return {
        "path": str(path),
        "valid": True,
        "document_count": len(docs),
        "kinds": kinds,
        "error": "",
    }


def _run_kubectl_dry_run(kustomize_dir: Path, *, kubectl: str = "kubectl") -> dict[str, Any]:
    executable = shutil.which(kubectl)
    if not executable:
        return {
            "available": False,
            "command": kubectl,
            "status": "skipped",
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    completed = subprocess.run(
        [executable, "kustomize", str(kustomize_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "available": True,
        "command": executable,
        "status": "passed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _run_release_gate_for_profile(
    profile_path: str,
    *,
    api_base: str,
    ai_base: str,
    backup_dir: str | None = None,
    restore_db: str | None = None,
    skip_network: bool = False,
    skip_backup: bool = False,
) -> dict[str, Any]:
    profile = load_site_profile(profile_path)
    profile_errors = validate_site_profile(profile)
    checks: list[tuple[str, bool, str]] = [
        ("site profile valid", not profile_errors, "; ".join(profile_errors) if profile_errors else "ok"),
        ("scenario engine importable", bool(_load_scenario_catalog()), "ok" if _load_scenario_catalog() else "unavailable"),
        ("dataset catalog importable", bool(_load_runtime_catalog()), "ok" if _load_runtime_catalog() else "unavailable"),
    ]

    if not skip_network:
        api_status, _ = _http_get(f"{api_base}/health")
        ai_status, _ = _http_get(f"{ai_base}/health")
        checks.append(("api reachable", api_status == 200, str(api_status)))
        checks.append(("ai reachable", ai_status == 200, str(ai_status)))

    drill_result: dict[str, Any] | None = None
    if not skip_backup:
        restore_target = restore_db or profile.backups.restore_test_database
        drill_result = _run_backup_drill(backup_dir or profile.backups.directory, None, restore_target)
        backup_ok = drill_result["backup"].get("status") == "success"
        restore_ok = drill_result["restore"] is None or drill_result["restore"].get("status") == "success"
        checks.append(("backup drill", backup_ok, drill_result["backup"].get("error", "ok")))
        checks.append(("restore drill", restore_ok, drill_result["restore"].get("error", "ok") if drill_result["restore"] else "skipped"))

    payload = {
        "profile_id": profile.profile_id,
        "site_id": profile.site.id,
        "deployment_mode": profile.deployment_mode,
        "checks": [
            {"name": name, "ok": ok, "detail": detail}
            for name, ok, detail in checks
        ],
        "backup_drill": drill_result,
    }
    payload["passed"] = all(item["ok"] for item in payload["checks"])
    return payload


def _run_rollout_acceptance_for_manifest(
    manifest_path: str,
    *,
    api_base: str,
    ai_base: str,
    csv_path: str,
    site_ids: list[str] | None = None,
    events: int = 10_000,
    batch_size: int = 256,
    warmup_events: int = 0,
    min_average_events_per_second: float = 1000.0,
    repeat_count: int = 1,
    backup_dir: str | None = None,
    restore_db: str | None = None,
    skip_network: bool = False,
    skip_backup: bool = False,
    report_dir: str | None = None,
) -> dict[str, Any]:
    manifest = load_project_manifest(manifest_path)
    manifest_errors = validate_project_manifest(manifest)
    selected_ids = site_ids if site_ids is not None else [site.site_id for site in manifest.sites]

    benchmark_matrix = run_site_profile_matrix(
        Path(manifest_path),
        Path(csv_path),
        site_ids=selected_ids,
        events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
        min_average_events_per_second=min_average_events_per_second,
        repeat_count=repeat_count,
    )
    benchmark_by_site = {run.site_id: run for run in benchmark_matrix.runs}

    sites: list[dict[str, Any]] = []
    for site in manifest.sites:
        if site.site_id not in selected_ids:
            continue
        release_gate = _run_release_gate_for_profile(
            site.profile_path,
            api_base=api_base,
            ai_base=ai_base,
            backup_dir=backup_dir,
            restore_db=restore_db,
            skip_network=skip_network,
            skip_backup=skip_backup,
        )
        benchmark = benchmark_by_site.get(site.site_id)
        benchmark_payload = None
        benchmark_passed = False
        if benchmark is not None:
            benchmark_payload = {
                "site_id": benchmark.site_id,
                "deployment_mode": benchmark.deployment_mode,
                "profile_path": benchmark.profile_path,
                "average_events_per_second": benchmark.average_events_per_second,
                "passed": benchmark.passed,
                "detail": benchmark.detail,
            }
            benchmark_passed = benchmark.passed
        sites.append(
            {
                "site_id": site.site_id,
                "profile_path": site.profile_path,
                "release_gate": release_gate,
                "benchmark": benchmark_payload,
                "passed": release_gate["passed"] and benchmark_passed,
            }
        )

    passed = not manifest_errors and benchmark_matrix.passed and all(item["passed"] for item in sites)
    return {
        "project_id": manifest.project_id,
        "name": manifest.name,
        "manifest_errors": manifest_errors,
        "baseline_csv": csv_path,
        "benchmark_matrix": {
            "passed": benchmark_matrix.passed,
            "runs": [
                {
                    "site_id": run.site_id,
                    "deployment_mode": run.deployment_mode,
                    "profile_path": run.profile_path,
                    "average_events_per_second": run.average_events_per_second,
                    "passed": run.passed,
                    "detail": run.detail,
                }
                for run in benchmark_matrix.runs
            ],
        },
        "sites": sites,
        "passed": passed,
        "report_dir": report_dir,
    }


def _run_local_kubernetes_rehearsal(
    manifest_path: str,
    *,
    site_ids: list[str] | None = None,
    export_dir: str | None = None,
    kubectl: str = "kubectl",
) -> dict[str, Any]:
    manifest = load_project_manifest(manifest_path)
    manifest_errors = validate_project_manifest(manifest)
    selected_ids = site_ids if site_ids is not None else [site.site_id for site in manifest.sites]
    rehearsal_root = Path(export_dir) if export_dir else Path(tempfile.mkdtemp(prefix="datastream-k8s-rehearsal-"))
    rehearsal_root.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    for site in manifest.sites:
        if site.site_id not in selected_ids:
            continue
        written = manifest.export_bundles(rehearsal_root, site_id=site.site_id, fmt="both", layout="kubernetes")
        site_root = rehearsal_root / site.site_id
        kube_dir = site_root / "kubernetes"
        required_files = [
            kube_dir / "configmap.yaml",
            kube_dir / "site-profile-configmap.yaml",
            kube_dir / "deployment.yaml",
            kube_dir / "service.yaml",
            kube_dir / "kustomization.yaml",
            kube_dir / "README.md",
            kube_dir / "helm" / "values.generated.yaml",
            kube_dir / "helm" / "README.md",
            kube_dir / "helm" / "install.sh",
        ]
        required_files_ok = all(path.exists() for path in required_files)
        yaml_reports = []
        yaml_valid = True
        for path in [item for item in written if item.suffix in {".yaml", ".yml"}]:
            report = _validate_yaml_documents(path)
            yaml_reports.append(report)
            yaml_valid = yaml_valid and report["valid"]
        helm_values = kube_dir / "helm" / "values.generated.yaml"
        if helm_values.exists():
            report = _validate_yaml_documents(helm_values)
            if report not in yaml_reports:
                yaml_reports.append(report)
            yaml_valid = yaml_valid and report["valid"]
        kubectl_result = _run_kubectl_dry_run(kube_dir, kubectl=kubectl)
        kubectl_passed = kubectl_result["status"] != "failed"
        accepted = bool(not manifest_errors and required_files_ok and yaml_valid and kubectl_passed)
        runs.append(
            {
                "site_id": site.site_id,
                "profile_path": site.profile_path,
                "export_dir": str(site_root),
                "kubernetes_dir": str(kube_dir),
                "required_files_ok": required_files_ok,
                "yaml_valid": yaml_valid,
                "yaml_reports": yaml_reports,
                "kubectl": kubectl_result,
                "accepted": accepted,
                "written": [str(path) for path in written],
            }
        )

    passed = not manifest_errors and all(run["accepted"] for run in runs)
    return {
        "project_id": manifest.project_id,
        "name": manifest.name,
        "manifest_errors": manifest_errors,
        "selected_site_ids": selected_ids,
        "export_root": str(rehearsal_root),
        "runs": runs,
        "passed": passed,
    }


def _write_rollout_acceptance_report(report_dir: str, payload: dict[str, Any]) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    summary_path = output_dir / "rollout-acceptance-summary.json"
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    written.append(summary_path)

    for site in payload.get("sites", []):
        site_path = output_dir / f"{site['site_id']}.json"
        site_path.write_text(json.dumps(site, indent=2), encoding="utf-8")
        written.append(site_path)

    return written


def _write_site_profile_matrix_report(report_dir: str, result: Any) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    host_profile = _host_profile()
    summary = {
        "host_profile": host_profile,
        "passed": result.passed,
        "runs": [
            {
                "site_id": run.site_id,
                "deployment_mode": run.deployment_mode,
                "profile_path": run.profile_path,
                "average_events_per_second": run.average_events_per_second,
                "median_events_per_second": run.median_events_per_second,
                "stdev_events_per_second": run.stdev_events_per_second,
                "min_events_per_second": run.min_events_per_second,
                "max_events_per_second": run.max_events_per_second,
                "repeat_count": run.repeat_count,
                "latency_p99_ms": run.latency_p99_ms,
                "passed": run.passed,
                "detail": run.detail,
            }
            for run in result.runs
        ],
    }
    summary_path = output_dir / "site-profile-matrix-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    written.append(summary_path)
    host_profile_path = output_dir / "host-profile.json"
    host_profile_path.write_text(json.dumps(host_profile, indent=2), encoding="utf-8")
    written.append(host_profile_path)
    for run in summary["runs"]:
        site_path = output_dir / f"{run['site_id']}.json"
        site_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
        written.append(site_path)
    return written


def _write_site_profile_calibration_report(report_dir: str, result: Any) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    host_profile = _host_profile()
    summary = {
        "host_profile": host_profile,
        "passed": result.passed,
        "benchmark": {
            "passed": result.benchmark.passed,
            "runs": [
                {
                    "site_id": run.site_id,
                    "deployment_mode": run.deployment_mode,
                    "profile_path": run.profile_path,
                    "average_events_per_second": run.average_events_per_second,
                    "median_events_per_second": run.median_events_per_second,
                    "stdev_events_per_second": run.stdev_events_per_second,
                    "min_events_per_second": run.min_events_per_second,
                    "max_events_per_second": run.max_events_per_second,
                    "repeat_count": run.repeat_count,
                    "latency_p99_ms": run.latency_p99_ms,
                    "passed": run.passed,
                    "detail": run.detail,
                }
                for run in result.benchmark.runs
            ],
        },
        "runs": [
            {
                "site_id": run.site_id,
                "deployment_mode": run.deployment_mode,
                "profile_path": run.profile_path,
                "observed_average_events_per_second": run.observed_average_events_per_second,
                "observed_median_events_per_second": run.observed_median_events_per_second,
                "observed_stdev_events_per_second": run.observed_stdev_events_per_second,
                "acceptance_threshold": run.acceptance_threshold,
                "headroom_events_per_second": run.headroom_events_per_second,
                "headroom_ratio": run.headroom_ratio,
                "recommended_min_average_events_per_second": run.recommended_min_average_events_per_second,
                "recommended_batch_size": run.recommended_batch_size,
                "passed": run.passed,
            }
            for run in result.runs
        ],
    }
    summary_path = output_dir / "site-profile-calibration-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    written.append(summary_path)
    host_profile_path = output_dir / "host-profile.json"
    host_profile_path.write_text(json.dumps(host_profile, indent=2), encoding="utf-8")
    written.append(host_profile_path)
    return written


def cmd_status(args: argparse.Namespace) -> int:
    api_base = args.api_base
    ai_base = args.ai_base
    print("Local Stream Engine status")
    print("=" * 40)

    api_status, api_body = _http_get(f"{api_base}/health")
    _print_row("API service", f"{api_base} -> {api_status} {api_body.get('status', 'n/a') if api_status else api_body.get('error', 'offline')}")

    ai_status, ai_body = _http_get(f"{ai_base}/health")
    _print_row("AI gateway", f"{ai_base} -> {ai_status} {ai_body.get('status', 'n/a') if ai_status else ai_body.get('error', 'offline')}")

    profile_path = getattr(args, "site_profile", None)
    if profile_path:
        try:
            profile = load_site_profile(profile_path)
            errors = validate_site_profile(profile)
            _print_row("site profile", profile_path)
            _print_row("deployment_mode", profile.deployment_mode)
            _print_row("runtime_mode", profile.runtime.mode)
            _print_row("site_profile_valid", "yes" if not errors else "no")
            if errors:
                _print_row("validation_errors", "; ".join(errors))
        except Exception as exc:
            _print_row("site profile", profile_path)
            _print_row("site_profile_valid", "no")
            _print_row("site_profile_error", exc)

    if args.json:
        payload = {"api": {"status": api_status, "body": api_body}, "ai": {"status": ai_status, "body": ai_body}}
        if profile_path:
            try:
                profile = load_site_profile(profile_path)
                errors = validate_site_profile(profile)
                payload["site_profile"] = {
                    "path": profile_path,
                    "profile": profile.to_dict(),
                    "errors": errors,
                    "valid": not errors,
                }
            except Exception as exc:
                payload["site_profile"] = {"path": profile_path, "errors": [str(exc)], "valid": False}
        print(json.dumps(payload, indent=2))
    return 0


def cmd_scenarios(args: argparse.Namespace) -> int:
    scenarios = _load_scenario_catalog()
    if not scenarios:
        print("Scenario engine unavailable (could not import services.scenarios.engine)")
        return 1
    print("Available scenarios")
    print("=" * 40)
    for s in scenarios:
        if isinstance(s, dict):
            sid = s.get("id", s.get("scenario_id", "?"))
            name = s.get("name", s.get("scenario_id", "?"))
            desc = s.get("description", "")
        else:
            sid = getattr(s, "id", getattr(s, "scenario_id", "?"))
            name = getattr(s, "name", getattr(s, "scenario_id", "?"))
            desc = getattr(s, "description", "")
        print(f"{sid:<22}{name}")
        if desc:
            print(f"{'':22}{desc}")
    return 0


def cmd_datasets(args: argparse.Namespace) -> int:
    sources = _load_runtime_catalog()
    if not sources:
        print("Dataset catalog unavailable (could not import runtime_catalog)")
        return 1
    if args.category:
        sources = [s for s in sources if s.category == args.category]
    print("Testing datasets")
    print("=" * 40)
    for s in sources:
        print(f"{s.dataset_id:<14}{s.name}  [{s.category}]")
        print(f"{'':14}signals: {s.signals}")
        print(f"{'':14}best for: {s.best_use}")
        print(f"{'':14}license required: {s.licensed}")
        print()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print("datastream-doctor checks")
    print("=" * 40)

    checks = [
        ("API service reachable", _http_get(f"{args.api_base}/health")[0] == 200),
        ("AI gateway reachable", _http_get(f"{args.ai_base}/health")[0] == 200),
        ("Scenario engine importable", bool(_load_scenario_catalog())),
        ("Dataset catalog importable", bool(_load_runtime_catalog())),
    ]

    all_ok = True
    for label, ok in checks:
        mark = "OK" if ok else "FAIL"
        print(f"{mark:<6}{label}")
        if not ok:
            all_ok = False

    return 0 if all_ok else 2


def cmd_config(args: argparse.Namespace) -> int:
    print("Effective control configuration")
    print("=" * 40)
    _print_row("DATASTREAM_API_BASE", args.api_base)
    _print_row("DATASTREAM_AI_BASE", args.ai_base)
    _print_row("API health", _http_get(f"{args.api_base}/health")[0])
    _print_row("AI health", _http_get(f"{args.ai_base}/health")[0])
    return 0


def cmd_site_profile(args: argparse.Namespace) -> int:
    profile = load_site_profile(args.path)
    errors = validate_site_profile(profile)
    payload = {
        "path": args.path,
        "profile": profile.to_dict(),
        "errors": errors,
        "valid": not errors,
    }
    if args.action == "show":
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Site profile")
            print("=" * 40)
            _print_row("path", args.path)
            _print_row("profile_id", profile.profile_id)
            _print_row("deployment_mode", profile.deployment_mode)
            _print_row("runtime_mode", profile.runtime.mode)
            _print_row("site_id", profile.site.id)
            _print_row("site_name", profile.site.name)
            _print_row("region", profile.site.region)
            _print_row("network_zone", profile.site.network_zone)
            _print_row("brokers", profile.runtime.kafka_brokers)
            _print_row("ai_provider", profile.runtime.ai.provider)
            _print_row("backup_dir", profile.backups.directory)
            _print_row("federation", profile.federation.enabled)
        return 0 if not errors else 1

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("site-profile validation")
        print("=" * 40)
        _print_row("path", args.path)
        _print_row("valid", "yes" if not errors else "no")
        if errors:
            for err in errors:
                print(f"ERROR  {err}")
    return 0 if not errors else 1


def cmd_backup_drill(args: argparse.Namespace) -> int:
    tables = _parse_tables(args.tables)
    result = _run_backup_drill(args.backup_dir, tables, args.restore_db)
    backup_ok = result["backup"].get("status") == "success"
    restore_ok = result["restore"] is None or result["restore"].get("status") == "success"
    ok = backup_ok and restore_ok
    written_reports: list[Path] = []
    if args.report_dir:
        written_reports = _write_backup_drill_report(args.report_dir, result)

    if args.json:
        if written_reports:
            result = {**result, "written_reports": [str(path) for path in written_reports]}
        print(json.dumps(result, indent=2))
    else:
        print("backup drill")
        print("=" * 40)
        _print_row("backup_status", result["backup"].get("status", "unknown"))
        _print_row("backup_path", result["backup"].get("path", result["backup"].get("error", "n/a")))
        _print_row("restore_status", result["restore"].get("status", "skipped") if result["restore"] else "skipped")
        _print_row("available_backups", len(result["backups"]))
        _print_row("wal_g_installed", result["wal_g"].get("installed"))
        if result.get("snapshot_comparison") is not None:
            _print_row("snapshot_match", "yes" if result["snapshot_comparison"].get("matched") else "no")
        if written_reports:
            _print_row("report_dir", args.report_dir)
            for path in written_reports:
                print(f"{'':6}report  {path}")
    return 0 if ok else 2


def cmd_backup_drill_matrix(args: argparse.Namespace) -> int:
    site_profiles = [part.strip() for part in args.site_profiles.split(",") if part.strip()]
    if not site_profiles:
        raise ValueError("--site-profiles must contain at least one site profile path")
    tables = _parse_tables(args.tables)
    result = _run_backup_drill_matrix(
        site_profiles,
        backup_dir=args.backup_dir,
        tables=tables,
        restore_db=args.restore_db,
    )
    written_reports: list[Path] = []
    if args.report_dir:
        written_reports = _write_backup_drill_matrix_report(args.report_dir, result)

    if args.json:
        if written_reports:
            result = {**result, "written_reports": [str(path) for path in written_reports]}
        print(json.dumps(result, indent=2))
    else:
        print("backup drill matrix")
        print("=" * 40)
        _print_row("site_profiles", len(result["runs"]))
        _print_row("passed", str(result["passed"]).lower())
        for run in result["runs"]:
            print(
                f"{'':6}{run['site_id']:<18}backup={run['backup_status']:<8} restore={run['restore_status']:<8} "
                f"backup_s={run['backup_elapsed_seconds']} restore_s={run['restore_elapsed_seconds']} "
                f"snapshot_match={str(run['snapshot_match']).lower()}"
            )
        if written_reports:
            _print_row("report_dir", args.report_dir)
            for path in written_reports:
                print(f"{'':6}report  {path}")
    return 0 if result["passed"] else 2


def cmd_local_phase_one(args: argparse.Namespace) -> int:
    site_profiles = [part.strip() for part in args.site_profiles.split(",") if part.strip()]
    if not site_profiles:
        raise ValueError("--site-profiles must contain at least one site profile path")
    site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
    tables = _parse_tables(args.tables)
    backup_result = _run_backup_drill_matrix(
        site_profiles,
        backup_dir=args.backup_dir,
        tables=tables,
        restore_db=args.restore_db,
    )
    benchmark_result = run_site_profile_matrix(
        Path(args.manifest),
        Path(args.csv),
        site_ids=site_ids,
        events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        min_average_events_per_second=args.min_average_events_per_second,
        repeat_count=args.repeat_count,
    )
    payload = {
        "phase": "local-phase-one",
        "site_profiles": site_profiles,
        "manifest": str(args.manifest),
        "baseline_csv": str(args.csv),
        "backup_drill": backup_result,
        "benchmark": _serialize_site_profile_matrix_result(benchmark_result),
        "acceptance": _serialize_local_phase_one_acceptance(backup_result, benchmark_result),
        "passed": backup_result["passed"] and benchmark_result.passed,
    }
    payload["summary"] = _summarize_local_phase_one_acceptance(payload["acceptance"])
    written_reports: list[Path] = []
    if args.report_dir:
        written_reports = _write_local_phase_one_report(args.report_dir, payload)

    if args.json:
        if written_reports:
            payload = {**payload, "written_reports": [str(path) for path in written_reports]}
        print(json.dumps(payload, indent=2))
    else:
        print("local phase one")
        print("=" * 40)
        _print_row("passed", str(payload["passed"]).lower())
        _print_row("backup_passed", str(backup_result["passed"]).lower())
        _print_row("benchmark_passed", str(benchmark_result.passed).lower())
        _print_row("site_profiles", len(site_profiles))
        _print_row("acceptance_rows", len(payload["acceptance"]))
        _print_row("profile_summaries", payload["summary"]["site_profile_count"])
        _print_row("profiles_passed", payload["summary"]["passed_site_profiles"])
        for row in payload["acceptance"]:
            print(
                f"{'':6}{row['site_id']:<18}backup_rto={row['backup_rto_seconds']}<={row['backup_rto_threshold_seconds']} "
                f"restore_rto={row['restore_rto_seconds']}<={row['restore_rto_threshold_seconds']} "
                f"rpo={row['rpo_seconds']}<={row['rpo_threshold_seconds']} benchmark={row['benchmark_average_events_per_second']}"
            )
        for mode, mode_summary in payload["summary"]["deployment_modes"].items():
            print(f"{'':6}mode={mode:<14} sites={mode_summary['site_profiles']} passed={mode_summary['passed_site_profiles']} failed={mode_summary['failed_site_profiles']}")
        if benchmark_result.runs:
            for run in benchmark_result.runs:
                print(
                    f"{'':6}{run.site_id:<18}avg={run.average_events_per_second} "
                    f"median={run.median_events_per_second} passed={str(run.passed).lower()}"
                )
        if written_reports:
            _print_row("report_dir", args.report_dir)
            for path in written_reports:
                print(f"{'':6}report  {path}")
    return 0 if payload["passed"] else 2


def cmd_local_kubernetes_rehearsal(args: argparse.Namespace) -> int:
    site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
    payload = _run_local_kubernetes_rehearsal(
        args.manifest,
        site_ids=site_ids,
        export_dir=args.export_dir,
        kubectl=args.kubectl,
    )
    written_reports: list[Path] = []
    if args.report_dir:
        written_reports = _write_local_kubernetes_rehearsal_report(args.report_dir, payload)
    if args.json:
        if written_reports:
            payload = {**payload, "written_reports": [str(path) for path in written_reports]}
        print(json.dumps(payload, indent=2))
    else:
        print("local kubernetes rehearsal")
        print("=" * 40)
        _print_row("project_id", payload["project_id"])
        _print_row("passed", str(payload["passed"]).lower())
        _print_row("site_profiles", len(payload["runs"]))
        _print_row("export_root", payload["export_root"])
        for run in payload["runs"]:
            kubectl_status = run["kubectl"]["status"]
            print(
                f"{'':6}{run['site_id']:<18}yaml={str(run['yaml_valid']).lower()} "
                f"required={str(run['required_files_ok']).lower()} kubectl={kubectl_status} "
                f"accepted={str(run['accepted']).lower()}"
            )
        if written_reports:
            _print_row("report_dir", args.report_dir)
            for path in written_reports:
                print(f"{'':6}report  {path}")
    return 0 if payload["passed"] else 2


def _parse_json_or_empty(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            parsed = yaml.safe_load(value)
    if not isinstance(parsed, dict):
        raise ValueError("JSON input must decode to an object")
    return parsed


def cmd_agent_runtime(args: argparse.Namespace) -> int:
    action = args.action
    if action == "contract":
        payload = build_agent_runtime_contract()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("agent runtime contract")
            print("=" * 40)
            _print_row("diagnostic_role", payload["diagnostic_policy"]["role"])
            _print_row("diagnostic_tools", len(payload["diagnostic_policy"]["allowed_tools"]))
            _print_row("action_role", payload["action_policy"]["role"])
            _print_row("action_approval_required", str(payload["action_policy"]["approval_required"]).lower())
        return 0

    if action == "diagnostic-probe":
        from services.common.agent_runtime import DiagnosticAgentRuntime

        runtime = DiagnosticAgentRuntime(
            actor_id=args.actor_id,
            site_id=args.site_id,
            approval_required=args.approval_required,
        )
        payload = runtime.record_tool_call(
            call_id=args.call_id,
            tool_name=args.tool_name,
            arguments=_parse_json_or_empty(args.arguments),
            result_summary=args.result_summary,
            metadata=_parse_json_or_empty(args.metadata),
        )
        result = {
            "allowed_tools": list(runtime.allowed_tools),
            "record": payload.to_dict(),
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("agent diagnostic probe")
            print("=" * 40)
            _print_row("actor_id", args.actor_id)
            _print_row("tool_name", args.tool_name)
            _print_row("approved", str(payload.approved).lower())
            _print_row("allowed_tools", len(runtime.allowed_tools))
        return 0

    if action == "action-request":
        from services.common.agent_runtime import SupervisedActionRuntime

        runtime = SupervisedActionRuntime(actor_id=args.actor_id, site_id=args.site_id)
        payload = runtime.request_action(
            action_id=args.action_id,
            action_name=args.action_name,
            target_resource=args.target_resource,
            requested_by=args.requested_by,
            details=_parse_json_or_empty(args.details),
        )
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("agent action request")
            print("=" * 40)
            _print_row("action_id", payload["action_id"])
            _print_row("action_name", payload["action_name"])
            _print_row("status", payload["status"])
            _print_row("site_id", payload["site_id"])
        return 0

    raise ValueError(f"unknown agent runtime action: {action}")


def cmd_release_gate(args: argparse.Namespace) -> int:
    payload = _run_release_gate_for_profile(
        args.site_profile,
        api_base=args.api_base,
        ai_base=args.ai_base,
        backup_dir=args.backup_dir,
        restore_db=args.restore_db,
        skip_network=args.skip_network,
        skip_backup=args.skip_backup,
    )
    passed = bool(payload["passed"])

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("release gate")
        print("=" * 40)
        _print_row("profile_id", payload["profile_id"])
        _print_row("site_id", payload["site_id"])
        _print_row("deployment_mode", payload["deployment_mode"])
        for item in payload["checks"]:
            mark = "OK" if item["ok"] else "FAIL"
            print(f"{mark:<6}{item['name']:<22}{item['detail']}")
    return 0 if passed else 2


def cmd_project_manifest(args: argparse.Namespace) -> int:
    manifest = load_project_manifest(args.path)
    errors = validate_project_manifest(manifest)
    payload = {
        "path": args.path,
        "manifest": manifest.to_dict(),
        "errors": errors,
        "valid": not errors,
    }

    if args.action == "show":
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Project manifest")
            print("=" * 40)
            _print_row("path", args.path)
            _print_row("project_id", manifest.project_id)
            _print_row("name", manifest.name)
            _print_row("sites", len(manifest.sites))
            _print_row("sources", len(manifest.sources))
            _print_row("bridge_rules", len(manifest.bridge_rules))
            _print_row("correlation_groups", len(manifest.correlation_groups))
            _print_row("historian_days", manifest.retention.historian_days)
        return 0 if not errors else 1

    if args.action == "sites":
        if args.json:
            print(json.dumps({"sites": [site.to_dict() for site in manifest.sites]}, indent=2))
        else:
            print("Project sites")
            print("=" * 40)
            for site in manifest.sites:
                print(f"{site.site_id:<22}{site.profile_path}")
                if site.label:
                    print(f"{'':22}{site.label}")
        return 0 if not errors else 1

    if args.action == "bundle":
        bundle = manifest.bundle_for_site(args.site_id)
        if args.json:
            print(json.dumps(bundle, indent=2))
        else:
            print("Project bundle")
            print("=" * 40)
            _print_row("project_id", bundle["project_id"])
            _print_row("name", bundle["name"])
            if "site_id" in bundle:
                _print_row("site_id", bundle["site_id"])
                _print_row("site_profile", bundle["site_profile"])
                print("env:")
                for key, value in sorted(bundle["env"].items()):
                    print(f"  {key}={value}")
            else:
                for site in bundle["sites"]:
                    print(f"{site['site_id']:<22}{site['site_profile']}")
        return 0 if not errors else 1

    if args.action == "export":
        written = manifest.export_bundles(
            Path(args.output_dir),
            site_id=args.site_id,
            fmt=args.format,
            layout=args.layout,
        )
        payload = {
            "path": args.path,
            "output_dir": args.output_dir,
            "site_id": args.site_id,
            "format": args.format,
            "layout": args.layout,
            "written": [str(path) for path in written],
            "errors": errors,
            "valid": not errors,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("project export")
            print("=" * 40)
            _print_row("output_dir", args.output_dir)
            _print_row("format", args.format)
            _print_row("layout", args.layout)
            for path in written:
                print(path)
            if errors:
                for err in errors:
                    print(f"ERROR  {err}")
        return 0 if not errors else 1

    if args.action == "package":
        written = manifest.export_package(Path(args.output_dir), site_id=args.site_id, fmt=args.format)
        payload = {
            "path": args.path,
            "output_dir": args.output_dir,
            "site_id": args.site_id,
            "format": args.format,
            "written": [str(path) for path in written],
            "errors": errors,
            "valid": not errors,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("project package")
            print("=" * 40)
            _print_row("output_dir", args.output_dir)
            _print_row("format", args.format)
            for path in written:
                print(path)
            if errors:
                for err in errors:
                    print(f"ERROR  {err}")
        return 0 if not errors else 1

    if args.action == "release-package":
        if not args.site_id:
            raise ValueError("site_id is required for release-package")
        signing_key = None
        if args.sign:
            signing_key = os.getenv(args.signing_key_env)
            if not signing_key:
                raise ValueError(f"{args.signing_key_env} is required when --sign is set")
        written = manifest.export_release_artifact(
            Path(args.output_dir),
            site_id=args.site_id,
            fmt=args.format,
            signing_key=signing_key,
            signing_key_id=args.signing_key_env,
        )
        payload = {
            "path": args.path,
            "output_dir": args.output_dir,
            "site_id": args.site_id,
            "format": args.format,
            "signed": bool(signing_key),
            "written": [str(path) for path in written],
            "errors": errors,
            "valid": not errors,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("project release package")
            print("=" * 40)
            _print_row("output_dir", args.output_dir)
            _print_row("format", args.format)
            _print_row("site_id", args.site_id)
            _print_row("signed", "yes" if signing_key else "no")
            for path in written:
                print(path)
            if errors:
                for err in errors:
                    print(f"ERROR  {err}")
        return 0 if not errors else 1

    if args.action == "lint":
        issues = manifest.lint()
        passed = not issues
        payload = {
            "path": args.path,
            "issues": issues,
            "valid": passed,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("project lint")
            print("=" * 40)
            _print_row("path", args.path)
            _print_row("valid", "yes" if passed else "no")
            for issue in issues:
                print(f"ISSUE  {issue}")
        return 0 if passed else 2

    if args.action == "release-gate":
        checks: list[dict[str, Any]] = []
        for site in manifest.sites:
            result = _run_release_gate_for_profile(
                site.profile_path,
                api_base=args.api_base,
                ai_base=args.ai_base,
                backup_dir=args.backup_dir,
                restore_db=args.restore_db,
                skip_network=args.skip_network,
                skip_backup=args.skip_backup,
            )
            checks.append(
                {
                    "site_id": site.site_id,
                    "profile_path": site.profile_path,
                    "passed": result["passed"],
                    "checks": result["checks"],
                    "backup_drill": result["backup_drill"],
                }
            )
        passed = not errors and all(item["passed"] for item in checks)
        payload = {
            "project_id": manifest.project_id,
            "name": manifest.name,
            "manifest_errors": errors,
            "sites": checks,
            "passed": passed,
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("project release gate")
            print("=" * 40)
            _print_row("project_id", manifest.project_id)
            _print_row("name", manifest.name)
            for item in checks:
                mark = "OK" if item["passed"] else "FAIL"
                print(f"{mark:<6}{item['site_id']:<22}{item['profile_path']}")
                for check in item["checks"]:
                    inner_mark = "OK" if check["ok"] else "FAIL"
                    print(f"{'':6}{inner_mark:<6}{check['name']:<22} {check['detail']}")
            if errors:
                for err in errors:
                    print(f"ERROR  {err}")
        return 0 if passed else 2

    if args.action == "rollout-acceptance":
        site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
        payload = _run_rollout_acceptance_for_manifest(
            args.path,
            api_base=args.api_base,
            ai_base=args.ai_base,
            csv_path=args.csv,
            site_ids=site_ids,
            events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            min_average_events_per_second=args.min_average_events_per_second,
            repeat_count=args.repeat_count,
            backup_dir=args.backup_dir,
            restore_db=args.restore_db,
            skip_network=args.skip_network,
            skip_backup=args.skip_backup,
            report_dir=args.report_dir,
        )
        written_reports: list[Path] = []
        if args.report_dir:
            written_reports = _write_rollout_acceptance_report(args.report_dir, payload)
        if args.json:
            if written_reports:
                payload = {**payload, "written_reports": [str(path) for path in written_reports]}
            print(json.dumps(payload, indent=2))
        else:
            print("project rollout acceptance")
            print("=" * 40)
            _print_row("project_id", payload["project_id"])
            _print_row("name", payload["name"])
            _print_row("benchmark_csv", payload["baseline_csv"])
            if written_reports:
                _print_row("report_dir", args.report_dir)
                for path in written_reports:
                    print(f"{'':6}report  {path}")
            for item in payload["sites"]:
                mark = "OK" if item["passed"] else "FAIL"
                print(f"{mark:<6}{item['site_id']:<22}{item['profile_path']}")
                release_gate = item["release_gate"]
                release_mark = "OK" if release_gate["passed"] else "FAIL"
                print(f"{'':6}{release_mark:<6}release-gate")
                for check in release_gate["checks"]:
                    inner_mark = "OK" if check["ok"] else "FAIL"
                    print(f"{'':12}{inner_mark:<6}{check['name']:<22} {check['detail']}")
                benchmark = item["benchmark"]
                if benchmark is None:
                    print(f"{'':6}FAIL  benchmark unavailable")
                else:
                    benchmark_mark = "OK" if benchmark["passed"] else "FAIL"
                    print(
                        f"{'':6}{benchmark_mark:<6}benchmark avg={benchmark['average_events_per_second']:.2f} "
                        f"threshold={args.min_average_events_per_second}"
                    )
                    print(f"{'':12}{benchmark['detail']}")
            for err in payload["manifest_errors"]:
                print(f"ERROR  {err}")
        return 0 if payload["passed"] else 2

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("project-manifest validation")
        print("=" * 40)
        _print_row("path", args.path)
        _print_row("valid", "yes" if not errors else "no")
        if errors:
            for err in errors:
                print(f"ERROR  {err}")
    return 0 if not errors else 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    if args.action == "deployment-pack":
        result = run_deployment_pack_benchmark(
            Path(args.manifest),
            Path(args.csv),
            site_id=args.site_id,
            target_events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
        )
        if args.json:
            print(json.dumps(
                {
                    "manifest": result.manifest_path,
                    "csv": result.csv_path,
                    "site_id": result.site_id,
                    "export_elapsed_seconds": result.export_elapsed_seconds,
                    "export_file_count": result.export_file_count,
                    "export_files_per_second": result.export_files_per_second,
                    "systemd_file_count": result.systemd_file_count,
                    "kubernetes_file_count": result.kubernetes_file_count,
                    "replay_events": result.replay_events,
                    "replay_events_per_second": result.replay_events_per_second,
                    "replay_batches": result.replay_batches,
                    "replay_serialized_bytes": result.replay_serialized_bytes,
                },
                indent=2,
            ))
        else:
            print("deployment pack benchmark")
            print("=" * 40)
            print(format_deployment_pack_result(result))
        return 0
    if args.action == "deployment-pack-matrix":
        site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
        result = run_deployment_pack_matrix(
            Path(args.manifest),
            Path(args.csv),
            site_ids=site_ids,
            target_events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
        )
        if args.json:
            print(json.dumps({"runs": [asdict(item) for item in result]}, indent=2))
        else:
            print("deployment pack benchmark matrix")
            print("=" * 40)
            print(format_deployment_pack_matrix_result(result))
        return 0
    if args.action == "real-world-simulator":
        case_ids = [part.strip() for part in args.cases.split(",") if part.strip()] if args.cases else None
        result = run_real_world_simulator_suite(
            baseline_csv=Path(args.csv),
            events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            cases=case_ids,
        )
        if args.json:
            print(json.dumps(
                {
                    "cases": [
                        {
                            "case_id": item.case_id,
                            "source": item.source,
                            "scenario": item.scenario,
                            "events": item.events,
                            "invalid_events": item.invalid_events,
                            "batches": item.batches,
                            "elapsed_seconds": item.elapsed_seconds,
                            "events_per_second": item.events_per_second,
                            "serialized_bytes": item.serialized_bytes,
                        }
                        for item in result.cases
                    ],
                    "average_events_per_second": result.average_events_per_second,
                },
                indent=2,
            ))
        else:
            print("real-world simulator benchmark")
            print("=" * 40)
            print(format_real_world_simulator_result(result))
        return 0
    if args.action == "site-profile-matrix":
        site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
        result = run_site_profile_matrix(
            Path(args.manifest),
            Path(args.csv),
            site_ids=site_ids,
            events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            min_average_events_per_second=args.min_average_events_per_second,
            repeat_count=args.repeat_count,
        )
        written_reports: list[Path] = []
        if args.report_dir:
            written_reports = _write_site_profile_matrix_report(args.report_dir, result)
        if args.json:
            payload = {
                "passed": result.passed,
                "runs": [
                    {
                        "site_id": item.site_id,
                        "deployment_mode": item.deployment_mode,
                        "profile_path": item.profile_path,
                        "average_events_per_second": item.average_events_per_second,
                        "median_events_per_second": item.median_events_per_second,
                        "stdev_events_per_second": item.stdev_events_per_second,
                        "min_events_per_second": item.min_events_per_second,
                        "max_events_per_second": item.max_events_per_second,
                        "repeat_count": item.repeat_count,
                        "passed": item.passed,
                        "detail": item.detail,
                    }
                    for item in result.runs
                ],
            }
            if written_reports:
                payload["written_reports"] = [str(path) for path in written_reports]
            print(json.dumps(payload, indent=2))
        else:
            print("site profile benchmark matrix")
            print("=" * 40)
            print(format_site_profile_matrix_result(result))
            if written_reports:
                _print_row("report_dir", args.report_dir)
                for path in written_reports:
                    print(f"{'':6}report  {path}")
        return 0 if result.passed else 2
    if args.action == "site-profile-calibration":
        site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
        result = run_site_profile_calibration(
            Path(args.manifest),
            Path(args.csv),
            site_ids=site_ids,
            events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            min_average_events_per_second=args.min_average_events_per_second,
            repeat_count=args.repeat_count,
        )
        written_reports: list[Path] = []
        if args.report_dir:
            written_reports = _write_site_profile_calibration_report(args.report_dir, result)
        if args.json:
            payload = {
                "passed": result.passed,
                "benchmark": {
                    "passed": result.benchmark.passed,
                    "runs": [
                        {
                            "site_id": item.site_id,
                            "deployment_mode": item.deployment_mode,
                            "profile_path": item.profile_path,
                            "average_events_per_second": item.average_events_per_second,
                            "median_events_per_second": item.median_events_per_second,
                            "stdev_events_per_second": item.stdev_events_per_second,
                            "min_events_per_second": item.min_events_per_second,
                            "max_events_per_second": item.max_events_per_second,
                            "repeat_count": item.repeat_count,
                            "passed": item.passed,
                            "detail": item.detail,
                        }
                        for item in result.benchmark.runs
                    ],
                },
                "runs": [
                    {
                        "site_id": item.site_id,
                        "deployment_mode": item.deployment_mode,
                        "profile_path": item.profile_path,
                        "observed_average_events_per_second": item.observed_average_events_per_second,
                        "observed_median_events_per_second": item.observed_median_events_per_second,
                        "observed_stdev_events_per_second": item.observed_stdev_events_per_second,
                        "acceptance_threshold": item.acceptance_threshold,
                        "headroom_events_per_second": item.headroom_events_per_second,
                        "headroom_ratio": item.headroom_ratio,
                        "recommended_min_average_events_per_second": item.recommended_min_average_events_per_second,
                        "recommended_batch_size": item.recommended_batch_size,
                        "passed": item.passed,
                    }
                    for item in result.runs
                ],
            }
            if written_reports:
                payload["written_reports"] = [str(path) for path in written_reports]
            print(json.dumps(payload, indent=2))
        else:
            print("site profile calibration")
            print("=" * 40)
            print(format_site_profile_calibration_result(result))
            if written_reports:
                _print_row("report_dir", args.report_dir)
                for path in written_reports:
                    print(f"{'':6}report  {path}")
        return 0 if result.passed else 2
    if args.action == "cgr-gap-report":
        site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
        result = run_cgr_gap_report(
            Path(args.manifest),
            Path(args.csv),
            site_ids=site_ids,
            events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            min_average_events_per_second=args.min_average_events_per_second,
            cgr_target_events_per_second=args.cgr_events_per_second,
            cgr_target_p99_ms=args.cgr_p99_ms,
            documented_full_pipeline_events_per_second=args.documented_full_pipeline_events_per_second,
        )
        if args.json:
            print(json.dumps(
                {
                    "cgr_target_events_per_second": result.cgr_target_events_per_second,
                    "cgr_target_p99_ms": result.cgr_target_p99_ms,
                    "documented_full_pipeline_events_per_second": result.documented_full_pipeline_events_per_second,
                    "documented_full_pipeline_note": result.documented_full_pipeline_note,
                    "mixed_replay": {
                        "csv_path": result.mixed_replay.csv_path,
                        "events": result.mixed_replay.events,
                        "invalid_events": result.mixed_replay.invalid_events,
                        "batches": result.mixed_replay.batches,
                        "batch_size": result.mixed_replay.batch_size,
                        "elapsed_seconds": result.mixed_replay.elapsed_seconds,
                        "events_per_second": result.mixed_replay.events_per_second,
                        "serialized_bytes": result.mixed_replay.serialized_bytes,
                    },
                    "cgr_stream_slice": {
                        "csv_path": result.cgr_stream_slice.csv_path,
                        "events": result.cgr_stream_slice.events,
                        "invalid_events": result.cgr_stream_slice.invalid_events,
                        "batches": result.cgr_stream_slice.batches,
                        "batch_size": result.cgr_stream_slice.batch_size,
                        "window_limit": result.cgr_stream_slice.window_limit,
                        "elapsed_seconds": result.cgr_stream_slice.elapsed_seconds,
                        "events_per_second": result.cgr_stream_slice.events_per_second,
                        "serialized_bytes": result.cgr_stream_slice.serialized_bytes,
                        "raw_bytes": result.cgr_stream_slice.raw_bytes,
                        "normalized_bytes": result.cgr_stream_slice.normalized_bytes,
                        "processed_bytes": result.cgr_stream_slice.processed_bytes,
                        "latency_p99_ms": result.cgr_stream_slice.latency_p99_ms,
                    },
                    "flink_runtime_slice": {
                        "csv_path": result.flink_runtime_slice.csv_path,
                        "events": result.flink_runtime_slice.events,
                        "invalid_events": result.flink_runtime_slice.invalid_events,
                        "batches": result.flink_runtime_slice.batches,
                        "batch_size": result.flink_runtime_slice.batch_size,
                        "window_limit": result.flink_runtime_slice.window_limit,
                        "elapsed_seconds": result.flink_runtime_slice.elapsed_seconds,
                        "events_per_second": result.flink_runtime_slice.events_per_second,
                        "serialized_bytes": result.flink_runtime_slice.serialized_bytes,
                        "raw_bytes": result.flink_runtime_slice.raw_bytes,
                        "normalized_bytes": result.flink_runtime_slice.normalized_bytes,
                        "processed_bytes": result.flink_runtime_slice.processed_bytes,
                        "latency_p99_ms": result.flink_runtime_slice.latency_p99_ms,
                    },
                    "end_to_end_json": {
                        "csv_path": result.end_to_end_json.csv_path,
                        "wire_format": result.end_to_end_json.wire_format,
                        "events": result.end_to_end_json.events,
                        "invalid_events": result.end_to_end_json.invalid_events,
                        "batches": result.end_to_end_json.batches,
                        "batch_size": result.end_to_end_json.batch_size,
                        "window_limit": result.end_to_end_json.window_limit,
                        "elapsed_seconds": result.end_to_end_json.elapsed_seconds,
                        "events_per_second": result.end_to_end_json.events_per_second,
                        "payload_bytes": result.end_to_end_json.payload_bytes,
                        "roundtrip_bytes": result.end_to_end_json.roundtrip_bytes,
                        "latency_p99_ms": result.end_to_end_json.latency_p99_ms,
                    },
                    "end_to_end_msgpack": {
                        "csv_path": result.end_to_end_msgpack.csv_path,
                        "wire_format": result.end_to_end_msgpack.wire_format,
                        "events": result.end_to_end_msgpack.events,
                        "invalid_events": result.end_to_end_msgpack.invalid_events,
                        "batches": result.end_to_end_msgpack.batches,
                        "batch_size": result.end_to_end_msgpack.batch_size,
                        "window_limit": result.end_to_end_msgpack.window_limit,
                        "elapsed_seconds": result.end_to_end_msgpack.elapsed_seconds,
                        "events_per_second": result.end_to_end_msgpack.events_per_second,
                        "payload_bytes": result.end_to_end_msgpack.payload_bytes,
                        "roundtrip_bytes": result.end_to_end_msgpack.roundtrip_bytes,
                        "latency_p99_ms": result.end_to_end_msgpack.latency_p99_ms,
                    },
                    "real_world_simulator": {
                        "average_events_per_second": result.real_world_simulator.average_events_per_second,
                        "cases": [
                            {
                                "case_id": case.case_id,
                                "source": case.source,
                                "scenario": case.scenario,
                                "events": case.events,
                                "invalid_events": case.invalid_events,
                                "batches": case.batches,
                                "elapsed_seconds": case.elapsed_seconds,
                                "events_per_second": case.events_per_second,
                                "serialized_bytes": case.serialized_bytes,
                            }
                            for case in result.real_world_simulator.cases
                        ],
                    },
                    "site_profile_matrix": {
                        "passed": result.site_profile_matrix.passed,
                        "runs": [
                            {
                                "site_id": run.site_id,
                                "deployment_mode": run.deployment_mode,
                                "profile_path": run.profile_path,
                                "average_events_per_second": run.average_events_per_second,
                                "passed": run.passed,
                                "detail": run.detail,
                            }
                            for run in result.site_profile_matrix.runs
                        ],
                    },
                    "metrics": [
                        {
                            "label": metric.label,
                            "observed_events_per_second": metric.observed_events_per_second,
                            "target_events_per_second": metric.target_events_per_second,
                            "gap_multiplier": metric.gap_multiplier,
                            "gap_events_per_second": metric.gap_events_per_second,
                            "gap_percent": metric.gap_percent,
                            "note": metric.note,
                        }
                        for metric in result.metrics
                    ],
                    "latency_metrics": [
                        {
                            "label": metric.label,
                            "observed_p99_ms": metric.observed_p99_ms,
                            "target_p99_ms": metric.target_p99_ms,
                            "gap_ms": metric.gap_ms,
                            "gap_percent": metric.gap_percent,
                            "note": metric.note,
                        }
                        for metric in result.latency_metrics
                    ],
                    "latency_note": result.latency_note,
                },
                indent=2,
            ))
        else:
            print("cgr gap report")
            print("=" * 40)
            print(format_cgr_gap_result(result))
        return 0
    if args.action == "cgr-stream-slice":
        result = run_cgr_stream_slice_benchmark(
            Path(args.csv),
            target_events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            window_limit=args.window_limit,
        )
        if args.json:
            print(json.dumps(
                {
                    "csv_path": result.csv_path,
                    "events": result.events,
                    "invalid_events": result.invalid_events,
                    "batches": result.batches,
                    "batch_size": result.batch_size,
                    "window_limit": result.window_limit,
                    "elapsed_seconds": result.elapsed_seconds,
                    "events_per_second": result.events_per_second,
                    "serialized_bytes": result.serialized_bytes,
                    "raw_bytes": result.raw_bytes,
                    "normalized_bytes": result.normalized_bytes,
                    "processed_bytes": result.processed_bytes,
                    "latency_p50_ms": result.latency_p50_ms,
                    "latency_p95_ms": result.latency_p95_ms,
                    "latency_p99_ms": result.latency_p99_ms,
                    "latency_max_ms": result.latency_max_ms,
                    "stage_breakdown": [
                        {
                            "name": stage.name,
                            "operations": stage.operations,
                            "elapsed_seconds": stage.elapsed_seconds,
                            "events_per_second": stage.events_per_second,
                            "avg_ms": stage.avg_ms,
                            "latency_p50_ms": stage.latency_p50_ms,
                            "latency_p95_ms": stage.latency_p95_ms,
                            "latency_p99_ms": stage.latency_p99_ms,
                            "latency_max_ms": stage.latency_max_ms,
                        }
                        for stage in result.stage_breakdown
                    ],
                },
                indent=2,
            ))
        else:
            print("cgr stream slice benchmark")
            print("=" * 40)
            print(format_cgr_stream_slice_result(result))
        return 0
    if args.action == "flink-runtime-slice":
        result = run_flink_runtime_slice_benchmark(
            Path(args.csv),
            target_events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            window_limit=args.window_limit,
        )
        if args.json:
            print(json.dumps(
                {
                    "csv_path": result.csv_path,
                    "events": result.events,
                    "invalid_events": result.invalid_events,
                    "batches": result.batches,
                    "batch_size": result.batch_size,
                    "window_limit": result.window_limit,
                    "elapsed_seconds": result.elapsed_seconds,
                    "events_per_second": result.events_per_second,
                    "serialized_bytes": result.serialized_bytes,
                    "raw_bytes": result.raw_bytes,
                    "normalized_bytes": result.normalized_bytes,
                    "processed_bytes": result.processed_bytes,
                    "latency_p50_ms": result.latency_p50_ms,
                    "latency_p95_ms": result.latency_p95_ms,
                    "latency_p99_ms": result.latency_p99_ms,
                    "latency_max_ms": result.latency_max_ms,
                    "stage_breakdown": [
                        {
                            "name": stage.name,
                            "operations": stage.operations,
                            "elapsed_seconds": stage.elapsed_seconds,
                            "events_per_second": stage.events_per_second,
                            "avg_ms": stage.avg_ms,
                            "latency_p50_ms": stage.latency_p50_ms,
                            "latency_p95_ms": stage.latency_p95_ms,
                            "latency_p99_ms": stage.latency_p99_ms,
                            "latency_max_ms": stage.latency_max_ms,
                        }
                        for stage in result.stage_breakdown
                    ],
                },
                indent=2,
            ))
        else:
            print("flink runtime slice benchmark")
            print("=" * 40)
            print(format_flink_runtime_slice_result(result))
        return 0
    if args.action == "semantic-graph-slice":
        result = run_semantic_graph_slice_benchmark(
            Path(args.hierarchy),
            iterations=args.iterations,
            warmup_iterations=args.warmup_iterations,
        )
        if args.json:
            print(json.dumps(
                {
                    "hierarchy_path": result.hierarchy_path,
                    "iterations": result.iterations,
                    "warmup_iterations": result.warmup_iterations,
                    "entity_count": result.entity_count,
                    "relationship_count": result.relationship_count,
                    "measurement_count": result.measurement_count,
                    "elapsed_seconds": result.elapsed_seconds,
                    "graphs_per_second": result.graphs_per_second,
                    "entities_per_second": result.entities_per_second,
                    "relationships_per_second": result.relationships_per_second,
                },
                indent=2,
            ))
        else:
            print("semantic graph slice benchmark")
            print("=" * 40)
            print(format_semantic_graph_slice_result(result))
        return 0
    if args.action == "semantic-graph-query":
        result = run_semantic_graph_query_benchmark(
            Path(args.hierarchy),
            iterations=args.iterations,
            warmup_iterations=args.warmup_iterations,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(
                {
                    "hierarchy_path": result.hierarchy_path,
                    "iterations": result.iterations,
                    "warmup_iterations": result.warmup_iterations,
                    "query_count": result.query_count,
                    "matched_entities": result.matched_entities,
                    "matched_relationships": result.matched_relationships,
                    "elapsed_seconds": result.elapsed_seconds,
                    "queries_per_second": result.queries_per_second,
                },
                indent=2,
            ))
        else:
            print("semantic graph query benchmark")
            print("=" * 40)
            print(format_semantic_graph_query_result(result))
        return 0
    if args.action == "semantic-store-write":
        result = run_semantic_store_write_benchmark(
            Path(args.store),
            iterations=args.iterations,
            warmup_iterations=args.warmup_iterations,
        )
        if args.json:
            print(json.dumps(
                {
                    "store_path": result.store_path,
                    "iterations": result.iterations,
                    "warmup_iterations": result.warmup_iterations,
                    "elapsed_seconds": result.elapsed_seconds,
                    "writes_per_second": result.writes_per_second,
                    "entity_count": result.entity_count,
                    "relationship_count": result.relationship_count,
                    "lineage_count": result.lineage_count,
                },
                indent=2,
            ))
        else:
            print("semantic store write benchmark")
            print("=" * 40)
            print(format_semantic_store_write_result(result))
        return 0
    if args.action == "production-pipeline":
        result = run_production_pipeline_benchmark(
            Path(args.csv),
            target_events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            window_limit=args.window_limit,
            runtime_mode=args.runtime_mode,
            wire_format=args.wire_format,
        )
        if args.json:
            print(json.dumps(
                {
                    "csv_path": result.csv_path,
                    "runtime_mode": result.runtime_mode,
                    "execution_path": result.execution_path,
                    "events": result.events,
                    "invalid_events": result.invalid_events,
                    "batches": result.batches,
                    "batch_size": result.batch_size,
                    "window_limit": result.window_limit,
                    "elapsed_seconds": result.elapsed_seconds,
                    "events_per_second": result.events_per_second,
                    "serialized_bytes": result.serialized_bytes,
                    "roundtrip_bytes": result.roundtrip_bytes,
                    "latency_p50_ms": result.latency_p50_ms,
                    "latency_p95_ms": result.latency_p95_ms,
                    "latency_p99_ms": result.latency_p99_ms,
                    "latency_max_ms": result.latency_max_ms,
                    "stage_breakdown": [
                        {
                            "name": stage.name,
                            "operations": stage.operations,
                            "elapsed_seconds": stage.elapsed_seconds,
                            "events_per_second": stage.events_per_second,
                            "avg_ms": stage.avg_ms,
                            "latency_p50_ms": stage.latency_p50_ms,
                            "latency_p95_ms": stage.latency_p95_ms,
                            "latency_p99_ms": stage.latency_p99_ms,
                            "latency_max_ms": stage.latency_max_ms,
                        }
                        for stage in result.stage_breakdown
                    ],
                },
                indent=2,
            ))
        else:
            print("production pipeline benchmark")
            print("=" * 40)
            print(format_production_pipeline_result(result))
        return 0
    if args.action == "end-to-end-pipeline":
        result = run_end_to_end_pipeline_benchmark(
            Path(args.csv),
            target_events=args.events,
            batch_size=args.batch_size,
            warmup_events=args.warmup_events,
            window_limit=args.window_limit,
            wire_format=args.wire_format,
        )
        if args.json:
            print(json.dumps(
                {
                    "csv_path": result.csv_path,
                    "wire_format": result.wire_format,
                    "events": result.events,
                    "invalid_events": result.invalid_events,
                    "batches": result.batches,
                    "batch_size": result.batch_size,
                    "window_limit": result.window_limit,
                    "elapsed_seconds": result.elapsed_seconds,
                    "events_per_second": result.events_per_second,
                    "payload_bytes": result.payload_bytes,
                    "roundtrip_bytes": result.roundtrip_bytes,
                    "latency_p50_ms": result.latency_p50_ms,
                    "latency_p95_ms": result.latency_p95_ms,
                    "latency_p99_ms": result.latency_p99_ms,
                    "latency_max_ms": result.latency_max_ms,
                    "stage_breakdown": [
                        {
                            "name": stage.name,
                            "operations": stage.operations,
                            "elapsed_seconds": stage.elapsed_seconds,
                            "events_per_second": stage.events_per_second,
                            "avg_ms": stage.avg_ms,
                            "latency_p50_ms": stage.latency_p50_ms,
                            "latency_p95_ms": stage.latency_p95_ms,
                            "latency_p99_ms": stage.latency_p99_ms,
                            "latency_max_ms": stage.latency_max_ms,
                        }
                        for stage in result.stage_breakdown
                    ],
                },
                indent=2,
            ))
        else:
            print("end to end pipeline benchmark")
            print("=" * 40)
            print(format_end_to_end_pipeline_result(result))
        return 0
    raise ValueError(f"unknown benchmark action: {args.action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datastreamctl",
        description="Admin/control CLI for Local Stream Engine.",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API service base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--ai-base", default=DEFAULT_AI_BASE, help=f"AI gateway base URL (default: {DEFAULT_AI_BASE})")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show runtime status of API and AI services")
    status.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
    status.set_defaults(func=cmd_status)
    status_json = sub.add_parser("status-json", help="Show runtime status as JSON")
    status_json.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
    status_json.set_defaults(func=cmd_status)
    status_json.add_argument("--json", action="store_true", default=True)

    sub.add_parser("scenarios", help="List available scenarios").set_defaults(func=cmd_scenarios)

    datasets_cmd = sub.add_parser("datasets", help="List testing datasets")
    datasets_cmd.add_argument("--category", default=None, help="Filter by category (mock, synthetic, industrial, security, multimodal)")
    datasets_cmd.set_defaults(func=cmd_datasets)

    sub.add_parser("doctor", help="Run health/diagnostic checks").set_defaults(func=cmd_doctor)
    sub.add_parser("config", help="Show effective control configuration").set_defaults(func=cmd_config)

    agent_runtime = sub.add_parser("agent-runtime", help="Inspect the read-only diagnostic runtime and supervised action scaffold")
    agent_runtime_sub = agent_runtime.add_subparsers(dest="action", required=True)
    agent_contract = agent_runtime_sub.add_parser("contract", help="Show the current agent runtime contract")
    agent_contract.add_argument("--json", action="store_true")
    agent_contract.set_defaults(func=cmd_agent_runtime)
    agent_probe = agent_runtime_sub.add_parser("diagnostic-probe", help="Record a read-only diagnostic tool call")
    agent_probe.add_argument("--actor-id", default="diagnostic-agent")
    agent_probe.add_argument("--site-id", default="")
    agent_probe.add_argument("--tool-name", default="historian.recent_events")
    agent_probe.add_argument("--call-id", default="probe-1")
    agent_probe.add_argument("--arguments", default="{}")
    agent_probe.add_argument("--result-summary", default="probe")
    agent_probe.add_argument("--metadata", default="{}")
    agent_probe.add_argument("--approval-required", action="store_true")
    agent_probe.add_argument("--json", action="store_true")
    agent_probe.set_defaults(func=cmd_agent_runtime)
    agent_action = agent_runtime_sub.add_parser("action-request", help="Record a supervised action request")
    agent_action.add_argument("--actor-id", default="supervised-action-agent")
    agent_action.add_argument("--site-id", default="")
    agent_action.add_argument("--action-id", default="action-1")
    agent_action.add_argument("--action-name", default="feature-plan")
    agent_action.add_argument("--target-resource", default="site:demo-site")
    agent_action.add_argument("--requested-by", default="operator")
    agent_action.add_argument("--details", default="{}")
    agent_action.add_argument("--json", action="store_true")
    agent_action.set_defaults(func=cmd_agent_runtime)

    site_profile = sub.add_parser("site-profile", help="Show or validate a site profile")
    site_profile_sub = site_profile.add_subparsers(dest="action", required=True)
    site_show = site_profile_sub.add_parser("show", help="Show parsed site profile values")
    site_show.add_argument("path")
    site_show.add_argument("--json", action="store_true")
    site_show.set_defaults(func=cmd_site_profile)
    site_validate = site_profile_sub.add_parser("validate", help="Validate a site profile")
    site_validate.add_argument("path")
    site_validate.add_argument("--json", action="store_true")
    site_validate.set_defaults(func=cmd_site_profile)

    backup = sub.add_parser("backup-drill", help="Run a historian backup/restore drill")
    backup.add_argument("--backup-dir", default=None)
    backup.add_argument("--tables", default=None, help="Comma-separated table names")
    backup.add_argument("--restore-db", default=None, help="Optional restore target database")
    backup.add_argument("--report-dir", default=None, help="Optional directory to write backup drill reports")
    backup.add_argument("--json", action="store_true")
    backup.set_defaults(func=cmd_backup_drill)

    backup_matrix = sub.add_parser("backup-drill-matrix", help="Run backup/restore drills across multiple site profiles")
    backup_matrix.add_argument("--site-profiles", required=True, help="Comma-separated site profile YAML paths")
    backup_matrix.add_argument("--backup-dir", default=None)
    backup_matrix.add_argument("--tables", default=None, help="Comma-separated table names")
    backup_matrix.add_argument("--restore-db", default=None, help="Optional restore target database")
    backup_matrix.add_argument("--report-dir", default=None, help="Optional directory to write backup drill reports")
    backup_matrix.add_argument("--json", action="store_true")
    backup_matrix.set_defaults(func=cmd_backup_drill_matrix)

    local_phase_one = sub.add_parser("local-phase-one", help="Run a local restore/rollback and benchmark phase gate")
    local_phase_one.add_argument("--site-profiles", default="config/site-profiles/single-site.yaml,config/site-profiles/plant-local.yaml")
    local_phase_one.add_argument("--manifest", default="config/project-manifest.yaml")
    local_phase_one.add_argument("--csv", default="data/benchmarks/industrial_mixed_benchmark.csv")
    local_phase_one.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    local_phase_one.add_argument("--events", type=int, default=10_000)
    local_phase_one.add_argument("--batch-size", type=int, default=256)
    local_phase_one.add_argument("--warmup-events", type=int, default=0)
    local_phase_one.add_argument("--repeat-count", type=int, default=1)
    local_phase_one.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    local_phase_one.add_argument("--backup-dir", default=None)
    local_phase_one.add_argument("--tables", default=None, help="Comma-separated table names")
    local_phase_one.add_argument("--restore-db", default=None, help="Optional restore target database")
    local_phase_one.add_argument("--report-dir", default=None, help="Optional directory to write phase reports")
    local_phase_one.add_argument("--json", action="store_true")
    local_phase_one.set_defaults(func=cmd_local_phase_one)

    local_k8s = sub.add_parser("local-kubernetes-rehearsal", help="Validate generated Kubernetes bundles for a local release rehearsal")
    local_k8s.add_argument("--manifest", default="config/project-manifest.yaml")
    local_k8s.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    local_k8s.add_argument("--export-dir", default=None, help="Directory where generated Kubernetes bundles are written")
    local_k8s.add_argument("--kubectl", default="kubectl", help="kubectl executable to use for optional dry-run validation")
    local_k8s.add_argument("--report-dir", default=None, help="Optional directory to write rehearsal reports")
    local_k8s.add_argument("--json", action="store_true")
    local_k8s.set_defaults(func=cmd_local_kubernetes_rehearsal)

    release = sub.add_parser("release-gate", help="Run production readiness checks for one site profile")
    release.add_argument("site_profile", help="Path to the site profile YAML")
    release.add_argument("--backup-dir", default=None)
    release.add_argument("--restore-db", default=None)
    release.add_argument("--skip-network", action="store_true")
    release.add_argument("--skip-backup", action="store_true")
    release.add_argument("--json", action="store_true")
    release.set_defaults(func=cmd_release_gate)

    project = sub.add_parser("project-manifest", help="Show or validate a project manifest")
    project_sub = project.add_subparsers(dest="action", required=True)
    project_show = project_sub.add_parser("show", help="Show parsed project manifest values")
    project_show.add_argument("path")
    project_show.add_argument("--json", action="store_true")
    project_show.set_defaults(func=cmd_project_manifest)
    project_validate = project_sub.add_parser("validate", help="Validate a project manifest")
    project_validate.add_argument("path")
    project_validate.add_argument("--json", action="store_true")
    project_validate.set_defaults(func=cmd_project_manifest)
    project_sites = project_sub.add_parser("sites", help="List sites in a project manifest")
    project_sites.add_argument("path")
    project_sites.add_argument("--json", action="store_true")
    project_sites.set_defaults(func=cmd_project_manifest)
    project_bundle = project_sub.add_parser("bundle", help="Print per-site environment bundles")
    project_bundle.add_argument("path")
    project_bundle.add_argument("--site-id", default=None, help="Optional site to print")
    project_bundle.add_argument("--json", action="store_true")
    project_bundle.set_defaults(func=cmd_project_manifest)
    project_export = project_sub.add_parser("export", help="Export per-site bundles to disk")
    project_export.add_argument("path")
    project_export.add_argument("output_dir")
    project_export.add_argument("--site-id", default=None, help="Optional site to export")
    project_export.add_argument("--format", choices=["env", "yaml", "both"], default="both")
    project_export.add_argument("--layout", choices=["flat", "systemd", "windows", "kubernetes"], default="flat")
    project_export.add_argument("--json", action="store_true")
    project_export.set_defaults(func=cmd_project_manifest)
    project_package = project_sub.add_parser("package", help="Export a combined deployment package for one site")
    project_package.add_argument("path")
    project_package.add_argument("output_dir")
    project_package.add_argument("--site-id", default=None, help="Optional site to package")
    project_package.add_argument("--format", choices=["env", "yaml", "both"], default="both")
    project_package.add_argument("--json", action="store_true")
    project_package.set_defaults(func=cmd_project_manifest)
    project_release_package = project_sub.add_parser("release-package", help="Export a release-artifact skeleton for one site")
    project_release_package.add_argument("path")
    project_release_package.add_argument("output_dir")
    project_release_package.add_argument("--site-id", required=True, help="Site to package into a release artifact")
    project_release_package.add_argument("--format", choices=["env", "yaml", "both"], default="both")
    project_release_package.add_argument("--sign", action="store_true", help="Write a release-signature.json using the configured signing key")
    project_release_package.add_argument("--signing-key-env", default="DATASTREAM_RELEASE_SIGNING_KEY", help="Environment variable that holds the signing key")
    project_release_package.add_argument("--json", action="store_true")
    project_release_package.set_defaults(func=cmd_project_manifest)
    project_lint = project_sub.add_parser("lint", help="Lint the project manifest for collisions and policy drift")
    project_lint.add_argument("path")
    project_lint.add_argument("--json", action="store_true")
    project_lint.set_defaults(func=cmd_project_manifest)
    project_release = project_sub.add_parser("release-gate", help="Run release-gate checks for all sites in a project manifest")
    project_release.add_argument("path")
    project_release.add_argument("--api-base", default=DEFAULT_API_BASE)
    project_release.add_argument("--ai-base", default=DEFAULT_AI_BASE)
    project_release.add_argument("--backup-dir", default=None)
    project_release.add_argument("--restore-db", default=None)
    project_release.add_argument("--skip-network", action="store_true")
    project_release.add_argument("--skip-backup", action="store_true")
    project_release.add_argument("--json", action="store_true")
    project_release.set_defaults(func=cmd_project_manifest)
    project_rollout = project_sub.add_parser("rollout-acceptance", help="Run release-gate and benchmark acceptance for all sites in a project manifest")
    project_rollout.add_argument("path")
    project_rollout.add_argument("--api-base", default=DEFAULT_API_BASE)
    project_rollout.add_argument("--ai-base", default=DEFAULT_AI_BASE)
    project_rollout.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    project_rollout.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    project_rollout.add_argument("--events", type=int, default=10_000)
    project_rollout.add_argument("--batch-size", type=int, default=256)
    project_rollout.add_argument("--warmup-events", type=int, default=0)
    project_rollout.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    project_rollout.add_argument("--repeat-count", type=int, default=1, help="Number of benchmark repeats per site")
    project_rollout.add_argument("--backup-dir", default=None)
    project_rollout.add_argument("--restore-db", default=None)
    project_rollout.add_argument("--report-dir", default=None, help="Optional directory to write JSON rollout acceptance reports")
    project_rollout.add_argument("--skip-network", action="store_true")
    project_rollout.add_argument("--skip-backup", action="store_true")
    project_rollout.add_argument("--json", action="store_true")
    project_rollout.set_defaults(func=cmd_project_manifest)

    benchmark = sub.add_parser("benchmark", help="Run performance benchmarks")
    benchmark_sub = benchmark.add_subparsers(dest="action", required=True)
    deployment_pack = benchmark_sub.add_parser("deployment-pack", help="Benchmark deployment exports and mock replay data")
    deployment_pack.add_argument("--manifest", default=str(Path("config/project-manifest.yaml")))
    deployment_pack.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    deployment_pack.add_argument("--site-id", default="demo-site")
    deployment_pack.add_argument("--events", type=int, default=10_000)
    deployment_pack.add_argument("--batch-size", type=int, default=256)
    deployment_pack.add_argument("--warmup-events", type=int, default=0)
    deployment_pack.add_argument("--json", action="store_true")
    deployment_pack.set_defaults(func=cmd_benchmark)
    deployment_pack_matrix = benchmark_sub.add_parser("deployment-pack-matrix", help="Benchmark deployment exports across multiple sites")
    deployment_pack_matrix.add_argument("--manifest", default=str(Path("config/project-manifest.yaml")))
    deployment_pack_matrix.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    deployment_pack_matrix.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    deployment_pack_matrix.add_argument("--events", type=int, default=10_000)
    deployment_pack_matrix.add_argument("--batch-size", type=int, default=256)
    deployment_pack_matrix.add_argument("--warmup-events", type=int, default=0)
    deployment_pack_matrix.add_argument("--json", action="store_true")
    deployment_pack_matrix.set_defaults(func=cmd_benchmark)
    real_world_simulator = benchmark_sub.add_parser("real-world-simulator", help="Benchmark simulated real-world industrial scenarios")
    real_world_simulator.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    real_world_simulator.add_argument("--events", type=int, default=10_000)
    real_world_simulator.add_argument("--batch-size", type=int, default=256)
    real_world_simulator.add_argument("--warmup-events", type=int, default=0)
    real_world_simulator.add_argument("--cases", default=None, help="Comma-separated cases: mock-normal,mock-drift,mock-spike,industrial-benchmark")
    real_world_simulator.add_argument("--json", action="store_true")
    real_world_simulator.set_defaults(func=cmd_benchmark)
    site_profile_matrix = benchmark_sub.add_parser("site-profile-matrix", help="Benchmark real-world simulator runs per site profile")
    site_profile_matrix.add_argument("--manifest", default=str(Path("config/project-manifest.yaml")))
    site_profile_matrix.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    site_profile_matrix.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    site_profile_matrix.add_argument("--events", type=int, default=10_000)
    site_profile_matrix.add_argument("--batch-size", type=int, default=256)
    site_profile_matrix.add_argument("--warmup-events", type=int, default=0)
    site_profile_matrix.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    site_profile_matrix.add_argument("--repeat-count", type=int, default=3, help="Number of repeated benchmark runs per site")
    site_profile_matrix.add_argument("--report-dir", default=None, help="Optional directory to write JSON benchmark reports")
    site_profile_matrix.add_argument("--json", action="store_true")
    site_profile_matrix.set_defaults(func=cmd_benchmark)
    site_profile_calibration = benchmark_sub.add_parser("site-profile-calibration", help="Calibrate per-site benchmark thresholds from the mixed replay pack")
    site_profile_calibration.add_argument("--manifest", default=str(Path("config/project-manifest.yaml")))
    site_profile_calibration.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    site_profile_calibration.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    site_profile_calibration.add_argument("--events", type=int, default=10_000)
    site_profile_calibration.add_argument("--batch-size", type=int, default=256)
    site_profile_calibration.add_argument("--warmup-events", type=int, default=0)
    site_profile_calibration.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    site_profile_calibration.add_argument("--repeat-count", type=int, default=3, help="Number of repeated benchmark runs per site")
    site_profile_calibration.add_argument("--report-dir", default=None, help="Optional directory to write JSON benchmark reports")
    site_profile_calibration.add_argument("--json", action="store_true")
    site_profile_calibration.set_defaults(func=cmd_benchmark)
    cgr_gap_report = benchmark_sub.add_parser("cgr-gap-report", help="Compare local benchmark results against the public CGR streaming claims")
    cgr_gap_report.add_argument("--manifest", default=str(Path("config/project-manifest.yaml")))
    cgr_gap_report.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    cgr_gap_report.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    cgr_gap_report.add_argument("--events", type=int, default=10_000)
    cgr_gap_report.add_argument("--batch-size", type=int, default=256)
    cgr_gap_report.add_argument("--warmup-events", type=int, default=0)
    cgr_gap_report.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    cgr_gap_report.add_argument("--cgr-events-per-second", type=float, default=2_000_000.0)
    cgr_gap_report.add_argument("--cgr-p99-ms", type=float, default=80.0)
    cgr_gap_report.add_argument("--documented-full-pipeline-events-per-second", type=float, default=125_830.0)
    cgr_gap_report.add_argument("--json", action="store_true")
    cgr_gap_report.set_defaults(func=cmd_benchmark)
    cgr_stream_slice = benchmark_sub.add_parser("cgr-stream-slice", help="Benchmark the isolated stream-processing slice used for CGR-style comparisons")
    cgr_stream_slice.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    cgr_stream_slice.add_argument("--events", type=int, default=10_000)
    cgr_stream_slice.add_argument("--batch-size", type=int, default=256)
    cgr_stream_slice.add_argument("--warmup-events", type=int, default=0)
    cgr_stream_slice.add_argument("--window-limit", type=int, default=25)
    cgr_stream_slice.add_argument("--json", action="store_true")
    cgr_stream_slice.set_defaults(func=cmd_benchmark)
    flink_runtime_slice = benchmark_sub.add_parser("flink-runtime-slice", help="Benchmark the keyed-state Flink runtime contract")
    flink_runtime_slice.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    flink_runtime_slice.add_argument("--events", type=int, default=10_000)
    flink_runtime_slice.add_argument("--batch-size", type=int, default=256)
    flink_runtime_slice.add_argument("--warmup-events", type=int, default=0)
    flink_runtime_slice.add_argument("--window-limit", type=int, default=25)
    flink_runtime_slice.add_argument("--json", action="store_true")
    flink_runtime_slice.set_defaults(func=cmd_benchmark)
    semantic_graph_slice = benchmark_sub.add_parser("semantic-graph-slice", help="Benchmark semantic graph projection from the industrial hierarchy")
    semantic_graph_slice.add_argument("--hierarchy", default=str(Path("config/assets.yaml")))
    semantic_graph_slice.add_argument("--iterations", type=int, default=1_000)
    semantic_graph_slice.add_argument("--warmup-iterations", type=int, default=100)
    semantic_graph_slice.add_argument("--json", action="store_true")
    semantic_graph_slice.set_defaults(func=cmd_benchmark)
    semantic_graph_query = benchmark_sub.add_parser("semantic-graph-query", help="Benchmark semantic graph query throughput")
    semantic_graph_query.add_argument("--hierarchy", default=str(Path("config/assets.yaml")))
    semantic_graph_query.add_argument("--iterations", type=int, default=1_000)
    semantic_graph_query.add_argument("--warmup-iterations", type=int, default=100)
    semantic_graph_query.add_argument("--limit", type=int, default=10)
    semantic_graph_query.add_argument("--json", action="store_true")
    semantic_graph_query.set_defaults(func=cmd_benchmark)
    semantic_store_write = benchmark_sub.add_parser("semantic-store-write", help="Benchmark semantic store write throughput")
    semantic_store_write.add_argument("--store", default=str(Path("data/semantic/semantic-store.json")))
    semantic_store_write.add_argument("--iterations", type=int, default=1_000)
    semantic_store_write.add_argument("--warmup-iterations", type=int, default=100)
    semantic_store_write.add_argument("--json", action="store_true")
    semantic_store_write.set_defaults(func=cmd_benchmark)
    production_pipeline = benchmark_sub.add_parser("production-pipeline", help="Benchmark the selected production runtime mode")
    production_pipeline.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    production_pipeline.add_argument("--events", type=int, default=10_000)
    production_pipeline.add_argument("--batch-size", type=int, default=256)
    production_pipeline.add_argument("--warmup-events", type=int, default=0)
    production_pipeline.add_argument("--window-limit", type=int, default=25)
    production_pipeline.add_argument("--runtime-mode", choices=("python-fallback", "flink-local", "flink-production"), default="python-fallback")
    production_pipeline.add_argument("--wire-format", choices=("json", "msgpack"), default="json")
    production_pipeline.add_argument("--json", action="store_true")
    production_pipeline.set_defaults(func=cmd_benchmark)
    end_to_end_pipeline = benchmark_sub.add_parser("end-to-end-pipeline", help="Benchmark the end-to-end pipeline with selectable wire format")
    end_to_end_pipeline.add_argument("--csv", default=str(Path("data/benchmarks/industrial_mixed_benchmark.csv")))
    end_to_end_pipeline.add_argument("--events", type=int, default=10_000)
    end_to_end_pipeline.add_argument("--batch-size", type=int, default=256)
    end_to_end_pipeline.add_argument("--warmup-events", type=int, default=0)
    end_to_end_pipeline.add_argument("--window-limit", type=int, default=25)
    end_to_end_pipeline.add_argument("--wire-format", choices=("json", "msgpack"), default="json")
    end_to_end_pipeline.add_argument("--json", action="store_true")
    end_to_end_pipeline.set_defaults(func=cmd_benchmark)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "json", False):
        args.json = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
