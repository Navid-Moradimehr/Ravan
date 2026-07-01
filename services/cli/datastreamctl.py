"""datastreamctl - admin/control CLI for Local Stream Engine.

Part of the Phase 8 distribution surface. Talks to the already-running
services (api_service on 8020, ai_gateway on 8080) and surfaces config,
health, scenario, and dataset information so operators can run the
platform from one command without a browser.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from pathlib import Path

from services.common.project_manifest import load_project_manifest, validate_project_manifest
from services.common.site_profiles import load_site_profile, validate_site_profile
from services.historian.backup import create_backup, get_walg_status, list_backups, restore_backup

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


def _parse_tables(value: str | None) -> list[str] | None:
    if not value:
        return None
    tables = [part.strip() for part in value.split(",") if part.strip()]
    return tables or None


def _run_backup_drill(backup_dir: str | None, tables: list[str] | None, restore_db: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "backup": create_backup(backup_dir=backup_dir, tables=tables),
        "restore": None,
        "backups": list_backups(backup_dir=backup_dir),
        "wal_g": get_walg_status(),
    }
    if result["backup"].get("status") != "success":
        return result
    if restore_db:
        result["restore"] = restore_backup(result["backup"]["path"], restore_db)
    return result


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


def cmd_status(args: argparse.Namespace) -> int:
    api_base = args.api_base
    ai_base = args.ai_base
    print("Local Stream Engine status")
    print("=" * 40)

    api_status, api_body = _http_get(f"{api_base}/health")
    _print_row("API service", f"{api_base} -> {api_status} {api_body.get('status', 'n/a') if api_status else api_body.get('error', 'offline')}")

    ai_status, ai_body = _http_get(f"{ai_base}/health")
    _print_row("AI gateway", f"{ai_base} -> {ai_status} {ai_body.get('status', 'n/a') if ai_status else ai_body.get('error', 'offline')}")

    if args.json:
        print(json.dumps({"api": {"status": api_status, "body": api_body}, "ai": {"status": ai_status, "body": ai_body}}, indent=2))
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
            _print_row("site_id", profile.site.id)
            _print_row("site_name", profile.site.name)
            _print_row("region", profile.site.region)
            _print_row("network_zone", profile.site.network_zone)
            _print_row("brokers", profile.runtime.redpanda_brokers)
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

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("backup drill")
        print("=" * 40)
        _print_row("backup_status", result["backup"].get("status", "unknown"))
        _print_row("backup_path", result["backup"].get("path", result["backup"].get("error", "n/a")))
        _print_row("restore_status", result["restore"].get("status", "skipped") if result["restore"] else "skipped")
        _print_row("available_backups", len(result["backups"]))
        _print_row("wal_g_installed", result["wal_g"].get("installed"))
    return 0 if ok else 2


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
        written = manifest.export_bundles(Path(args.output_dir), site_id=args.site_id, fmt=args.format)
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
            print("project export")
            print("=" * 40)
            _print_row("output_dir", args.output_dir)
            _print_row("format", args.format)
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
                    print(f"{'':6}{inner_mark:<6}{check['name']:<22}{check['detail']}")
            if errors:
                for err in errors:
                    print(f"ERROR  {err}")
        return 0 if passed else 2

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datastreamctl",
        description="Admin/control CLI for Local Stream Engine.",
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API service base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--ai-base", default=DEFAULT_AI_BASE, help=f"AI gateway base URL (default: {DEFAULT_AI_BASE})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show runtime status of API and AI services").set_defaults(func=cmd_status)
    status_json = sub.add_parser("status-json", help="Show runtime status as JSON")
    status_json.set_defaults(func=cmd_status)
    status_json.add_argument("--json", action="store_true", default=True)

    sub.add_parser("scenarios", help="List available scenarios").set_defaults(func=cmd_scenarios)

    datasets_cmd = sub.add_parser("datasets", help="List testing datasets")
    datasets_cmd.add_argument("--category", default=None, help="Filter by category (mock, synthetic, industrial, security, multimodal)")
    datasets_cmd.set_defaults(func=cmd_datasets)

    sub.add_parser("doctor", help="Run health/diagnostic checks").set_defaults(func=cmd_doctor)
    sub.add_parser("config", help="Show effective control configuration").set_defaults(func=cmd_config)

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
    backup.add_argument("--json", action="store_true")
    backup.set_defaults(func=cmd_backup_drill)

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
    project_export.add_argument("--json", action="store_true")
    project_export.set_defaults(func=cmd_project_manifest)
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "json", False):
        args.json = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
