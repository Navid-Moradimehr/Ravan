"""datastreamd - runtime supervisor for Local Stream Engine.

Launches the platform services (api_service, ai_gateway, edge_ingest,
processor, mock generator) as managed subprocesses and tracks their
lifecycle. Does NOT manage Docker infrastructure (Redpanda, Postgres,
Grafana) - that stays with docker compose for now.

Usage:
    python -m services.cli.datastreamd up
    python -m services.cli.datastreamd up --only api,ai
    python -m services.cli.datastreamd status
    python -m services.cli.datastreamd down
    python -m services.cli.datastreamd restart edge
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from services.common.project_manifest import load_project_manifest, validate_project_manifest
from services.common.site_profiles import load_site_profile, validate_site_profile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PID_DIR = Path(os.getenv("DATASTREAM_PID_DIR", PROJECT_ROOT / ".datastream"))
PID_FILE = PID_DIR / "processes.json"

PY = sys.executable


@dataclass
class ServiceSpec:
    name: str
    module: str
    description: str
    health_url: str
    depends_on: tuple[str, ...] = ()


SERVICE_SPECS: tuple[ServiceSpec, ...] = (
    ServiceSpec(
        name="api",
        module="services.api_service.main",
        description="REST API + WebSocket streams (port 8020)",
        health_url=f"{os.getenv('DATASTREAM_API_BASE', 'http://localhost:8020')}/health",
    ),
    ServiceSpec(
        name="ai",
        module="services.ai_gateway.main",
        description="AI gateway / LLM enrichment (port 8080)",
        health_url=f"{os.getenv('DATASTREAM_AI_BASE', 'http://localhost:8080')}/health",
    ),
    ServiceSpec(
        name="edge",
        module="services.edge_ingest.main",
        description="Protocol ingestion: OPC UA, MQTT, Modbus",
        health_url="",
        depends_on=(),
    ),
    ServiceSpec(
        name="processor",
        module="services.processor.runtime_processor",
        description="Stream processing and anomaly scoring",
        health_url="",
        depends_on=(),
    ),
    ServiceSpec(
        name="mock",
        module="services.datasets.mock_generator",
        description="Mock industrial data generator",
        health_url="",
        depends_on=(),
    ),
)

SPEC_BY_NAME = {s.name: s for s in SERVICE_SPECS}
DEFAULT_ORDER = [s.name for s in SERVICE_SPECS]


@dataclass
class ProcRecord:
    name: str
    pid: int
    module: str
    started_at: float
    health_url: str = ""
    site_profile: str = ""
    site_id: str = ""
    deployment_mode: str = ""
    project_manifest: str = ""
    project_id: str = ""


def _ensure_dir() -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)


def _load_records() -> dict[str, ProcRecord]:
    if not PID_FILE.exists():
        return {}
    try:
        raw = json.loads(PID_FILE.read_text())
        return {k: ProcRecord(**v) for k, v in raw.items()}
    except Exception:
        return {}


def _save_records(records: dict[str, ProcRecord]) -> None:
    _ensure_dir()
    PID_FILE.write_text(json.dumps({k: asdict(v) for k, v in records.items()}, indent=2))


def _is_alive(rec: ProcRecord) -> bool:
    if rec.pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {rec.pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return False
        output = result.stdout.strip()
        return bool(output and "No tasks are running" not in output and "INFO:" not in output)
    try:
        os.kill(rec.pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False
    return True


def _load_site_profile_context(path: str | None) -> tuple[dict[str, str], dict[str, str]]:
    if not path:
        return {}, {}
    profile = load_site_profile(path)
    errors = validate_site_profile(profile)
    if errors:
        raise ValueError(f"invalid site profile {path}: {'; '.join(errors)}")
    return (
        profile.to_env(),
        {
            "site_profile": str(path),
            "site_id": profile.site.id,
            "deployment_mode": profile.deployment_mode,
        },
    )


def _load_project_manifest_context(path: str | None, site_id: str | None = None) -> tuple[dict[str, str], dict[str, str]]:
    if not path:
        return {}, {}
    manifest = load_project_manifest(path)
    errors = validate_project_manifest(manifest)
    if errors:
        raise ValueError(f"invalid project manifest {path}: {'; '.join(errors)}")
    selected_site = None
    if site_id:
        for site in manifest.sites:
            if site.site_id == site_id:
                selected_site = site
                break
        if selected_site is None:
            raise ValueError(f"site_id {site_id} not found in project manifest {path}")
    else:
        if not manifest.sites:
            raise ValueError(f"project manifest {path} has no sites")
        selected_site = manifest.sites[0]
    profile = load_site_profile(selected_site.profile_path)
    profile_errors = validate_site_profile(profile)
    if profile_errors:
        raise ValueError(f"invalid site profile {selected_site.profile_path}: {'; '.join(profile_errors)}")
    env = profile.to_env()
    env.update(
        {
            "DATASTREAM_PROJECT_MANIFEST": str(path),
            "DATASTREAM_PROJECT_ID": manifest.project_id,
            "DATASTREAM_PROJECT_NAME": manifest.name,
            "DATASTREAM_PROJECT_RETENTION_DAYS": str(manifest.retention.historian_days),
        }
    )
    meta = {
        "project_manifest": str(path),
        "project_id": manifest.project_id,
        "site_profile": selected_site.profile_path,
        "site_id": selected_site.site_id,
        "deployment_mode": profile.deployment_mode,
    }
    return env, meta


def _start_one(spec: ServiceSpec, extra_env: dict[str, str] | None = None, profile_meta: dict[str, str] | None = None) -> ProcRecord | None:
    log_dir = PID_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{spec.name}.log"
    log_fp = open(log_path, "a", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.Popen(
            [PY, "-m", spec.module],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        print(f"[{spec.name}] failed to start: {exc}")
        return None
    print(f"[{spec.name}] started pid={proc.pid} module={spec.module} log={log_path}")
    return ProcRecord(
        name=spec.name,
        pid=proc.pid,
        module=spec.module,
        started_at=time.time(),
        health_url=spec.health_url,
        site_profile=(profile_meta or {}).get("site_profile", ""),
        site_id=(profile_meta or {}).get("site_id", ""),
        deployment_mode=(profile_meta or {}).get("deployment_mode", ""),
        project_manifest=(profile_meta or {}).get("project_manifest", ""),
        project_id=(profile_meta or {}).get("project_id", ""),
    )


def _resolve_order(names: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def visit(n: str) -> None:
        if n in seen or n not in SPEC_BY_NAME:
            return
        seen.add(n)
        dep = SPEC_BY_NAME[n]
        for d in dep.depends_on:
            visit(d)
        ordered.append(n)

    for n in names:
        visit(n)
    return ordered


def cmd_up(args: argparse.Namespace) -> int:
    records = _load_records()
    records = {k: v for k, v in records.items() if _is_alive(v)}
    extra_env, profile_meta = {}, {}
    if args.project_manifest:
        extra_env, profile_meta = _load_project_manifest_context(args.project_manifest, args.site_id)
    elif args.site_profile:
        extra_env, profile_meta = _load_site_profile_context(args.site_profile)

    if args.only:
        wanted = [n.strip() for n in args.only.split(",") if n.strip()]
    else:
        wanted = DEFAULT_ORDER[:]

    order = _resolve_order(wanted)
    started = 0
    for name in order:
        if name in records:
            print(f"[{name}] already running pid={records[name].pid}")
            continue
        spec = SPEC_BY_NAME[name]
        missing = [d for d in spec.depends_on if d not in records and d not in order]
        if missing:
            print(f"[{name}] skipping, missing dependencies: {missing}")
            continue
        rec = _start_one(spec, extra_env=extra_env, profile_meta=profile_meta)
        if rec:
            records[name] = rec
            started += 1
            if args.wait and spec.health_url:
                _wait_health(spec, args.wait)

    _save_records(records)
    print(f"started={started} managed={len(records)} pid_file={PID_FILE}")
    return 0


def _wait_health(spec: ServiceSpec, timeout: float) -> bool:
    if not spec.health_url:
        return False
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(spec.health_url, timeout=1.0) as resp:
                if 200 <= resp.status < 300:
                    print(f"[{spec.name}] health OK")
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"[{spec.name}] health check timed out after {timeout}s")
    return False


def cmd_down(args: argparse.Namespace) -> int:
    records = _load_records()
    stopped = 0
    targets = [n.strip() for n in args.only.split(",") if n.strip()] if args.only else list(records.keys())
    for name in targets:
        rec = records.get(name)
        if not rec or not _is_alive(rec):
            records.pop(name, None)
            continue
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(rec.pid), "/F", "/T"], check=False)
            else:
                os.killpg(os.getpgid(rec.pid), signal.SIGTERM)
            stopped += 1
            print(f"[{name}] stopped pid={rec.pid}")
        except ProcessLookupError:
            pass
        except Exception as exc:
            print(f"[{name}] stop error: {exc}")
        records.pop(name, None)
    _save_records(records)
    print(f"stopped={stopped} managed={len(records)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    records = _load_records()
    print("datastreamd managed services")
    print("=" * 56)
    any_dead = False
    for name in DEFAULT_ORDER:
        spec = SPEC_BY_NAME[name]
        rec = records.get(name)
        alive = bool(rec and _is_alive(rec))
        state = f"UP pid={rec.pid}" if alive and rec else "DOWN"
        if not alive:
            any_dead = True
        print(f"{name:<12}{state:<24}{spec.description}")
        if rec and (rec.site_id or rec.deployment_mode):
            print(f"{'':12}{'':24}site={rec.site_id or 'n/a'} mode={rec.deployment_mode or 'n/a'}")
        if rec and (rec.project_id or rec.project_manifest):
            print(f"{'':12}{'':24}project={rec.project_id or 'n/a'} manifest={rec.project_manifest or 'n/a'}")
        if args.json:
            pass
    if args.json:
        payload = {
            name: {
                "alive": bool(records.get(name) and _is_alive(records[name])),
                "pid": records[name].pid if records.get(name) else None,
                "module": spec.module,
                "site_id": records[name].site_id if records.get(name) else "",
                "deployment_mode": records[name].deployment_mode if records.get(name) else "",
                "site_profile": records[name].site_profile if records.get(name) else "",
            }
            for name, spec in ((n, SPEC_BY_NAME[n]) for n in DEFAULT_ORDER)
        }
        print(json.dumps(payload, indent=2))
    return 1 if any_dead and args.fail_on_down else 0


def cmd_restart(args: argparse.Namespace) -> int:
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    for name in names:
        if name not in SPEC_BY_NAME:
            print(f"[{name}] unknown service; choices: {list(SPEC_BY_NAME)}")
            return 2
    down_args = argparse.Namespace(only=",".join(names))
    cmd_down(down_args)
    up_args = argparse.Namespace(
        only=",".join(names),
        wait=args.wait,
        site_profile=args.site_profile,
        project_manifest=args.project_manifest,
        site_id=args.site_id,
    )
    cmd_up(up_args)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    name = args.service
    if name not in SPEC_BY_NAME:
        print(f"unknown service: {name}; choices: {list(SPEC_BY_NAME)}")
        return 2
    log_path = PID_DIR / "logs" / f"{name}.log"
    if not log_path.exists():
        print(f"no log file at {log_path}")
        return 1
    n = args.lines if args.lines and args.lines > 0 else 50
    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except Exception as exc:
        print(f"read error: {exc}")
        return 1
    for line in lines[-n:]:
        print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datastreamd",
        description="Runtime supervisor for Local Stream Engine services.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("up", help="Start managed services")
    up.add_argument("--only", default=None, help="Comma-separated subset to start")
    up.add_argument("--wait", type=float, default=0.0, help="Seconds to wait for each health check")
    up.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
    up.add_argument("--project-manifest", default=os.getenv("DATASTREAM_PROJECT_MANIFEST"), help="Optional project manifest YAML")
    up.add_argument("--site-id", default=os.getenv("DATASTREAM_SITE_ID"), help="Select a site from the project manifest")
    up.set_defaults(func=cmd_up)

    down = sub.add_parser("down", help="Stop managed services")
    down.add_argument("--only", default=None, help="Comma-separated subset to stop")
    down.set_defaults(func=cmd_down)

    status = sub.add_parser("status", help="Show service status")
    status.add_argument("--json", action="store_true")
    status.add_argument("--fail-on-down", action="store_true")
    status.set_defaults(func=cmd_status)

    restart = sub.add_parser("restart", help="Restart services")
    restart.add_argument("names", help="Comma-separated service names")
    restart.add_argument("--wait", type=float, default=0.0)
    restart.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
    restart.add_argument("--project-manifest", default=os.getenv("DATASTREAM_PROJECT_MANIFEST"), help="Optional project manifest YAML")
    restart.add_argument("--site-id", default=os.getenv("DATASTREAM_SITE_ID"), help="Select a site from the project manifest")
    restart.set_defaults(func=cmd_restart)

    logs = sub.add_parser("logs", help="Tail a service log")
    logs.add_argument("service", help="Service name")
    logs.add_argument("--lines", "-n", type=int, default=50)
    logs.set_defaults(func=cmd_logs)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
