"""Deployment preflight checks composed from existing platform validators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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
) -> PreflightReport:
    checks: list[PreflightCheck] = []
    checks.append(_path_check("compose file", Path(compose_file)))

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
