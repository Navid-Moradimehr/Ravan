"""datastreamd - runtime supervisor for Ravan.

Launches the platform services (api_service, ai_gateway, edge_ingest,
processor) as managed subprocesses and tracks their
lifecycle. Does NOT manage Docker infrastructure (Kafka, Postgres,
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
        name="flink-job",
        module="services.processor.iot_anomaly_job",
        description="Flink keyed-state stream processor",
        health_url="",
        depends_on=(),
    ),
    ServiceSpec(
        name="fanout",
        module="services.processor.normalized_fanout",
        description="Normalized fan-out consumer (industrial.normalized -> sinks)",
        health_url="",
        depends_on=(),
    ),
    ServiceSpec(
        name="ai-fanout",
        module="services.processor.ai_enriched_fanout",
        description="AI-enriched fan-out consumer (iot.ai_enriched -> historian)",
        health_url="",
        depends_on=(),
    ),
)

SPEC_BY_NAME = {s.name: s for s in SERVICE_SPECS}
DEFAULT_ORDER = [s.name for s in SERVICE_SPECS]


def _services_for_runtime_mode(runtime_mode: str | None) -> list[str]:
    mode = (runtime_mode or "python-fallback").strip().lower()
    if mode == "flink-production":
        return ["api", "ai", "edge", "fanout", "ai-fanout", "flink-job"]
    if mode == "flink-local":
        return ["api", "ai", "edge", "fanout", "ai-fanout", "flink-job"]
    return ["api", "ai", "edge", "processor", "fanout", "ai-fanout"]


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
    runtime_mode: str = ""
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
            "runtime_mode": profile.runtime.mode,
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
        "runtime_mode": profile.runtime.mode,
    }
    return env, meta


def _spawn_one(
    spec: ServiceSpec,
    extra_env: dict[str, str] | None = None,
    profile_meta: dict[str, str] | None = None,
    *,
    detached: bool,
) -> tuple[subprocess.Popen, ProcRecord, Any] | None:
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
            start_new_session=detached,
        )
    except Exception as exc:
        log_fp.close()
        print(f"[{spec.name}] failed to start: {exc}")
        return None
    record = ProcRecord(
        name=spec.name,
        pid=proc.pid,
        module=spec.module,
        started_at=time.time(),
        health_url=spec.health_url,
        site_profile=(profile_meta or {}).get("site_profile", ""),
        site_id=(profile_meta or {}).get("site_id", ""),
        deployment_mode=(profile_meta or {}).get("deployment_mode", ""),
        runtime_mode=(profile_meta or {}).get("runtime_mode", ""),
        project_manifest=(profile_meta or {}).get("project_manifest", ""),
        project_id=(profile_meta or {}).get("project_id", ""),
    )
    return proc, record, log_fp


def _start_one(spec: ServiceSpec, extra_env: dict[str, str] | None = None, profile_meta: dict[str, str] | None = None) -> ProcRecord | None:
    spawned = _spawn_one(spec, extra_env=extra_env, profile_meta=profile_meta, detached=True)
    if spawned is None:
        return None
    proc, record, _log_fp = spawned
    print(f"[{spec.name}] started pid={proc.pid} module={spec.module} log={PID_DIR / 'logs' / f'{spec.name}.log'}")
    return record


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
        wanted = _services_for_runtime_mode((profile_meta or {}).get("runtime_mode"))

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


def _terminate_process(proc: subprocess.Popen, timeout: float) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=max(0.1, timeout))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=max(0.1, timeout))


def cmd_supervise(args: argparse.Namespace) -> int:
    """Run the managed service set as a foreground OS-service process."""
    extra_env, profile_meta = {}, {}
    if args.project_manifest:
        extra_env, profile_meta = _load_project_manifest_context(args.project_manifest, args.site_id)
    elif args.site_profile:
        extra_env, profile_meta = _load_site_profile_context(args.site_profile)

    if args.only:
        wanted = [name.strip() for name in args.only.split(",") if name.strip()]
    else:
        wanted = _services_for_runtime_mode((profile_meta or {}).get("runtime_mode"))
    order = _resolve_order(wanted)
    children: dict[str, tuple[subprocess.Popen, ProcRecord, Any]] = {}
    restart_history: dict[str, list[float]] = {name: [] for name in order}
    stop_requested = False
    old_handlers: dict[int, Any] = {}

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            old_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, request_stop)
        except (AttributeError, ValueError):
            pass

    def launch(name: str) -> bool:
        spec = SPEC_BY_NAME[name]
        spawned = _spawn_one(spec, extra_env=extra_env, profile_meta=profile_meta, detached=False)
        if spawned is None:
            return False
        proc, record, log_fp = spawned
        children[name] = (proc, record, log_fp)
        _save_records({key: value[1] for key, value in children.items()})
        print(f"[{name}] supervised pid={proc.pid} module={spec.module} log={PID_DIR / 'logs' / f'{name}.log'}")
        if args.wait and spec.health_url:
            _wait_health(spec, args.wait)
        return True

    exit_code = 0
    try:
        for name in order:
            if not launch(name):
                print(f"[{name}] supervision could not start the service", file=sys.stderr)
                exit_code = 1
                stop_requested = True
                break

        while children and not stop_requested:
            for name, (proc, record, log_fp) in list(children.items()):
                return_code = proc.poll()
                if return_code is None:
                    continue
                log_fp.close()
                children.pop(name, None)
                history = restart_history[name]
                now = time.time()
                history[:] = [started_at for started_at in history if now - started_at < args.restart_window]
                history.append(now)
                print(f"[{name}] exited code={return_code}; restart {len(history)}/{args.max_restarts}", file=sys.stderr)
                if len(history) > args.max_restarts:
                    print(f"[{name}] restart budget exceeded; stopping supervision", file=sys.stderr)
                    exit_code = 1
                    stop_requested = True
                    break
                time.sleep(min(5.0, 0.5 * (2 ** min(len(history) - 1, 3))))
                if not stop_requested and not launch(name):
                    exit_code = 1
                    stop_requested = True
                    break
            _save_records({key: value[1] for key, value in children.items()})
            time.sleep(0.25)
    except KeyboardInterrupt:
        stop_requested = True
    finally:
        for proc, _record, log_fp in list(children.values()):
            _terminate_process(proc, args.shutdown_timeout)
            log_fp.close()
        children.clear()
        _save_records({})
        for sig, handler in old_handlers.items():
            try:
                signal.signal(sig, handler)
            except (AttributeError, ValueError):
                pass
    return exit_code


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
            print(
                f"{'':12}{'':24}site={rec.site_id or 'n/a'} mode={rec.deployment_mode or 'n/a'} "
                f"runtime={rec.runtime_mode or 'n/a'}"
            )
        if rec and (rec.project_id or rec.project_manifest):
            print(f"{'':12}{'':24}project={rec.project_id or 'n/a'} manifest={rec.project_manifest or 'n/a'}")
        if args.json:
            pass

    profile_path = getattr(args, "site_profile", None)
    if profile_path:
        try:
            profile = load_site_profile(profile_path)
            errors = validate_site_profile(profile)
            print(f"{'':12}{'':24}site_profile={profile_path}")
            print(f"{'':12}{'':24}runtime_mode={profile.runtime.mode}")
            print(f"{'':12}{'':24}site_profile_valid={'yes' if not errors else 'no'}")
            if errors:
                print(f"{'':12}{'':24}validation_errors={' ; '.join(errors)}")
        except Exception as exc:
            print(f"{'':12}{'':24}site_profile={profile_path}")
            print(f"{'':12}{'':24}site_profile_valid=no")
            print(f"{'':12}{'':24}site_profile_error={exc}")

    if args.json:
        payload = {
            name: {
                "alive": bool(records.get(name) and _is_alive(records[name])),
                "pid": records[name].pid if records.get(name) else None,
                "module": spec.module,
                "site_id": records[name].site_id if records.get(name) else "",
                "deployment_mode": records[name].deployment_mode if records.get(name) else "",
                "runtime_mode": records[name].runtime_mode if records.get(name) else "",
                "site_profile": records[name].site_profile if records.get(name) else "",
            }
            for name, spec in ((n, SPEC_BY_NAME[n]) for n in DEFAULT_ORDER)
        }
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
        description="Runtime supervisor for Ravan services.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("up", help="Start managed services")
    up.add_argument("--only", default=None, help="Comma-separated subset to start")
    up.add_argument("--wait", type=float, default=0.0, help="Seconds to wait for each health check")
    up.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
    up.add_argument("--project-manifest", default=os.getenv("DATASTREAM_PROJECT_MANIFEST"), help="Optional project manifest YAML")
    up.add_argument("--site-id", default=os.getenv("DATASTREAM_SITE_ID"), help="Select a site from the project manifest")
    up.set_defaults(func=cmd_up)

    supervise = sub.add_parser("supervise", help="Run managed services in the foreground for an OS service")
    supervise.add_argument("--only", default=None, help="Comma-separated subset to supervise")
    supervise.add_argument("--wait", type=float, default=0.0, help="Seconds to wait for each health check")
    supervise.add_argument("--max-restarts", type=int, default=5, help="Maximum restarts per service within the restart window")
    supervise.add_argument("--restart-window", type=float, default=60.0, help="Restart accounting window in seconds")
    supervise.add_argument("--shutdown-timeout", type=float, default=10.0, help="Seconds to wait before killing a child")
    supervise.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
    supervise.add_argument("--project-manifest", default=os.getenv("DATASTREAM_PROJECT_MANIFEST"), help="Optional project manifest YAML")
    supervise.add_argument("--site-id", default=os.getenv("DATASTREAM_SITE_ID"), help="Select a site from the project manifest")
    supervise.set_defaults(func=cmd_supervise)

    down = sub.add_parser("down", help="Stop managed services")
    down.add_argument("--only", default=None, help="Comma-separated subset to stop")
    down.set_defaults(func=cmd_down)

    status = sub.add_parser("status", help="Show service status")
    status.add_argument("--json", action="store_true")
    status.add_argument("--fail-on-down", action="store_true")
    status.add_argument("--site-profile", default=os.getenv("DATASTREAM_SITE_PROFILE"), help="Optional site profile YAML")
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
