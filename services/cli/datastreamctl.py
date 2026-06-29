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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "json", False):
        args.json = False
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
