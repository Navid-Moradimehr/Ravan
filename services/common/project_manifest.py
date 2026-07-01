from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from services.common.site_profiles import load_site_profile, validate_site_profile


VALID_BRIDGE_MODES = {"replicate", "fanout", "correlate", "rollup"}


@dataclass(frozen=True)
class ProjectSite:
    site_id: str
    profile_path: str
    label: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectSource:
    source_id: str
    site_id: str
    source_protocol: str
    asset_id: str
    line: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    topic: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BridgeRule:
    name: str
    mode: str
    from_sources: tuple[str, ...]
    to_sources: tuple[str, ...] = field(default_factory=tuple)
    topic_template: str = ""
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorrelationGroup:
    name: str
    members: tuple[str, ...]
    strategy: str = "site_asset_tag"
    window_minutes: int = 60
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectRetention:
    historian_days: int = 90
    raw_days: int = 30
    compressed_days: int = 7
    backup_days: int = 30

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectManifest:
    schema_version: int
    project_id: str
    name: str
    description: str = ""
    sites: tuple[ProjectSite, ...] = field(default_factory=tuple)
    sources: tuple[ProjectSource, ...] = field(default_factory=tuple)
    bridge_rules: tuple[BridgeRule, ...] = field(default_factory=tuple)
    correlation_groups: tuple[CorrelationGroup, ...] = field(default_factory=tuple)
    retention: ProjectRetention = field(default_factory=ProjectRetention)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "sites": [site.to_dict() for site in self.sites],
            "sources": [source.to_dict() for source in self.sources],
            "bridge_rules": [rule.to_dict() for rule in self.bridge_rules],
            "correlation_groups": [group.to_dict() for group in self.correlation_groups],
            "retention": self.retention.to_dict(),
        }

    def site_profile_paths(self) -> dict[str, Path]:
        return {site.site_id: Path(site.profile_path) for site in self.sites}

    def to_site_envs(self) -> dict[str, dict[str, str]]:
        envs: dict[str, dict[str, str]] = {}
        for site in self.sites:
            profile = load_site_profile(site.profile_path)
            errors = validate_site_profile(profile)
            if errors:
                raise ValueError(f"invalid site profile {site.profile_path}: {'; '.join(errors)}")
            env = profile.to_env()
            env["DATASTREAM_PROJECT_ID"] = self.project_id
            env["DATASTREAM_PROJECT_NAME"] = self.name
            env["DATASTREAM_PROJECT_RETENTION_DAYS"] = str(self.retention.historian_days)
            envs[site.site_id] = env
        return envs


def _load_tuple(items: Any, factory) -> tuple[Any, ...]:
    if not items:
        return ()
    return tuple(factory(item) for item in items)


def _load_site(data: dict[str, Any]) -> ProjectSite:
    return ProjectSite(
        site_id=str(data.get("site_id", "")).strip(),
        profile_path=str(data.get("profile_path", "")).strip(),
        label=str(data.get("label", "")).strip(),
        notes=str(data.get("notes", "")).strip(),
    )


def _load_source(data: dict[str, Any]) -> ProjectSource:
    return ProjectSource(
        source_id=str(data.get("source_id", "")).strip(),
        site_id=str(data.get("site_id", "")).strip(),
        source_protocol=str(data.get("source_protocol", "")).strip(),
        asset_id=str(data.get("asset_id", "")).strip(),
        line=str(data.get("line", "")).strip(),
        tags=tuple(str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()),
        topic=str(data.get("topic", "")).strip(),
        notes=str(data.get("notes", "")).strip(),
    )


def _load_bridge(data: dict[str, Any]) -> BridgeRule:
    return BridgeRule(
        name=str(data.get("name", "")).strip(),
        mode=str(data.get("mode", "")).strip(),
        from_sources=tuple(str(item).strip() for item in data.get("from_sources", []) if str(item).strip()),
        to_sources=tuple(str(item).strip() for item in data.get("to_sources", []) if str(item).strip()),
        topic_template=str(data.get("topic_template", "")).strip(),
        enabled=bool(data.get("enabled", True)),
        description=str(data.get("description", "")).strip(),
    )


def _load_group(data: dict[str, Any]) -> CorrelationGroup:
    return CorrelationGroup(
        name=str(data.get("name", "")).strip(),
        members=tuple(str(item).strip() for item in data.get("members", []) if str(item).strip()),
        strategy=str(data.get("strategy", "site_asset_tag")).strip(),
        window_minutes=int(data.get("window_minutes", 60)),
        description=str(data.get("description", "")).strip(),
    )


def _resolve_relative(base: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (base / candidate)


def load_project_manifest(path: Path | str) -> ProjectManifest:
    manifest_path = Path(path)
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    base_dir = manifest_path.parent.parent
    retention = data.get("retention") or {}
    raw_sites = data.get("sites") or []
    sites: list[ProjectSite] = []
    for raw in raw_sites:
        site = _load_site(raw)
        if site.profile_path:
            resolved = _resolve_relative(base_dir, site.profile_path)
            site = ProjectSite(
                site_id=site.site_id,
                profile_path=str(resolved),
                label=site.label,
                notes=site.notes,
            )
        sites.append(site)
    return ProjectManifest(
        schema_version=int(data.get("schema_version", 1)),
        project_id=str(data.get("project_id", "")).strip(),
        name=str(data.get("name", "")).strip(),
        description=str(data.get("description", "")).strip(),
        sites=tuple(sites),
        sources=_load_tuple(data.get("sources"), _load_source),
        bridge_rules=_load_tuple(data.get("bridge_rules"), _load_bridge),
        correlation_groups=_load_tuple(data.get("correlation_groups"), _load_group),
        retention=ProjectRetention(
            historian_days=int(retention.get("historian_days", 90)),
            raw_days=int(retention.get("raw_days", 30)),
            compressed_days=int(retention.get("compressed_days", 7)),
            backup_days=int(retention.get("backup_days", 30)),
        ),
    )


def validate_project_manifest(manifest: ProjectManifest) -> list[str]:
    errors: list[str] = []
    if manifest.schema_version != 1:
        errors.append(f"unsupported schema_version: {manifest.schema_version}")
    if not manifest.project_id:
        errors.append("project_id is required")
    if not manifest.name:
        errors.append("name is required")
    if not manifest.sites:
        errors.append("at least one site is required")

    site_ids = {site.site_id for site in manifest.sites}
    if len(site_ids) != len(manifest.sites):
        errors.append("site_id values must be unique")
    for site in manifest.sites:
        if not site.site_id:
            errors.append("site.site_id is required")
        if not site.profile_path:
            errors.append(f"{site.site_id or 'site'}: profile_path is required")
        elif not Path(site.profile_path).exists():
            errors.append(f"{site.site_id or 'site'}: profile_path does not exist: {site.profile_path}")
        else:
            profile = load_site_profile(site.profile_path)
            profile_errors = validate_site_profile(profile)
            if profile_errors:
                errors.extend(f"{site.site_id}: {err}" for err in profile_errors)

    source_ids = {source.source_id for source in manifest.sources}
    if len(source_ids) != len(manifest.sources):
        errors.append("source_id values must be unique")
    for source in manifest.sources:
        if not source.source_id:
            errors.append("source.source_id is required")
        if source.site_id and source.site_id not in site_ids:
            errors.append(f"source {source.source_id}: unknown site_id {source.site_id}")
        if not source.source_protocol:
            errors.append(f"source {source.source_id}: source_protocol is required")
        if not source.asset_id:
            errors.append(f"source {source.source_id}: asset_id is required")
        if not source.tags:
            errors.append(f"source {source.source_id}: at least one tag is required")

    for rule in manifest.bridge_rules:
        if not rule.name:
            errors.append("bridge rule name is required")
        if rule.mode not in VALID_BRIDGE_MODES:
            errors.append(f"bridge rule {rule.name or '?'}: mode must be one of {sorted(VALID_BRIDGE_MODES)}")
        if not rule.from_sources:
            errors.append(f"bridge rule {rule.name or '?'}: from_sources is required")
        if rule.mode in {"replicate", "fanout"} and not rule.to_sources:
            errors.append(f"bridge rule {rule.name or '?'}: to_sources is required for {rule.mode}")
        unknown_from = [item for item in rule.from_sources if item not in source_ids]
        unknown_to = [item for item in rule.to_sources if item not in source_ids]
        if unknown_from:
            errors.append(f"bridge rule {rule.name or '?'}: unknown from_sources {unknown_from}")
        if unknown_to:
            errors.append(f"bridge rule {rule.name or '?'}: unknown to_sources {unknown_to}")

    for group in manifest.correlation_groups:
        if not group.name:
            errors.append("correlation group name is required")
        if not group.members:
            errors.append(f"correlation group {group.name or '?'}: members is required")
        unknown = [item for item in group.members if item not in source_ids]
        if unknown:
            errors.append(f"correlation group {group.name or '?'}: unknown members {unknown}")
        if group.window_minutes < 1:
            errors.append(f"correlation group {group.name or '?'}: window_minutes must be >= 1")

    if manifest.retention.historian_days < manifest.retention.raw_days:
        errors.append("retention.historian_days must be >= retention.raw_days")
    if manifest.retention.raw_days < manifest.retention.compressed_days:
        errors.append("retention.raw_days must be >= retention.compressed_days")
    if manifest.retention.backup_days < 1:
        errors.append("retention.backup_days must be >= 1")
    return errors
