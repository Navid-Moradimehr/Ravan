"""Deployment preflight checks composed from existing platform validators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import os
import re

from services.common.project_manifest import load_project_manifest, validate_project_manifest
from services.common.site_profiles import load_site_profile, validate_site_profile
from services.benchmarks.industrial_soak import load_scenario


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    passed: bool
    checks: tuple[PreflightCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": [asdict(check) for check in self.checks]}


def _path_check(name: str, value: Path, *, must_exist: bool = True) -> PreflightCheck:
    exists = value.exists()
    passed = exists if must_exist else value.parent.exists()
    detail = str(value) if passed else f"path is not available: {value}"
    return PreflightCheck(name, passed, detail)


def run_preflight(
    *,
    site_profile: Path | str | None = None,
    project_manifest: Path | str | None = None,
    soak_scenario: Path | str | None = None,
    compose_file: Path | str = "docker/docker-compose.yml",
    strict: bool = False,
) -> PreflightReport:
    checks: list[PreflightCheck] = []
    compose_path = Path(compose_file)
    checks.append(_path_check("compose file", compose_path))
    if compose_path.exists():
        compose_text = compose_path.read_text(encoding="utf-8")
        floating = sorted(set(re.findall(r"image:\s*[^\n]*:(latest|latest-[^\s]+)", compose_text)))
        checks.append(PreflightCheck(
            "image tags pinned",
            not floating if strict else True,
            "no floating tags found" if not floating else f"WARNING: floating tags: {', '.join(floating)}",
        ))

    demo_defaults = {
        "POSTGRES_PASSWORD": "stream",
        "TIMESCALE_PASSWORD": "stream",
        "MINIO_ROOT_PASSWORD": "minio12345",
        "GF_SECURITY_ADMIN_PASSWORD": "admin",
    }
    for name, demo_value in demo_defaults.items():
        value = os.getenv(name)
        is_demo = value is None or value == demo_value
        checks.append(PreflightCheck(
            f"{name} configured",
            not is_demo if strict else True,
            "WARNING: development default or unset" if is_demo else "configured",
        ))

    if site_profile:
        path = Path(site_profile)
        checks.append(_path_check("site profile path", path))
        if path.exists():
            try:
                profile = load_site_profile(path)
                errors = validate_site_profile(profile)
                checks.append(PreflightCheck("site profile contract", not errors, "; ".join(errors) or f"site={profile.site.id}"))
            except Exception as exc:
                checks.append(PreflightCheck("site profile contract", False, f"could not parse profile: {exc}"))

    if project_manifest:
        path = Path(project_manifest)
        checks.append(_path_check("project manifest path", path))
        if path.exists():
            try:
                manifest = load_project_manifest(path)
                errors = validate_project_manifest(manifest)
                checks.append(PreflightCheck("project manifest contract", not errors, "; ".join(errors) or f"sites={len(manifest.sites)} sources={len(manifest.sources)}"))
            except Exception as exc:
                checks.append(PreflightCheck("project manifest contract", False, f"could not parse manifest: {exc}"))

    if soak_scenario:
        path = Path(soak_scenario)
        checks.append(_path_check("soak scenario path", path))
        if path.exists():
            try:
                scenario = load_scenario(path)
                checks.append(PreflightCheck("soak scenario contract", True, f"scenario={scenario.scenario_id} rate={scenario.configured_events_per_second:g}/s"))
            except Exception as exc:
                checks.append(PreflightCheck("soak scenario contract", False, f"could not parse scenario: {exc}"))

    return PreflightReport(passed=all(check.passed for check in checks), checks=tuple(checks))
