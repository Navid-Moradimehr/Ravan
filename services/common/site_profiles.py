from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


VALID_DEPLOYMENT_MODES = {"single-site", "plant-local", "federated"}
VALID_RUNTIME_MODES = {"python-fallback", "flink-local", "flink-production"}


@dataclass(frozen=True)
class SiteIdentity:
    id: str
    name: str
    region: str
    network_zone: str


@dataclass(frozen=True)
class AIBackendProfile:
    provider: str
    endpoint_url: str
    model_id: str
    local_only: bool


@dataclass(frozen=True)
class RuntimeProfile:
    image_tag: str
    mode: str
    redpanda_brokers: str
    historian_backend: str
    ai: AIBackendProfile


@dataclass(frozen=True)
class BackupPolicy:
    directory: str
    schedule: str
    retention_days: int
    restore_test_database: str | None


@dataclass(frozen=True)
class FederationProfile:
    enabled: bool
    export_mode: str
    central_endpoint: str | None


@dataclass(frozen=True)
class SiteProfile:
    schema_version: int
    profile_id: str
    deployment_mode: str
    site: SiteIdentity
    runtime: RuntimeProfile
    backups: BackupPolicy
    federation: FederationProfile

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_env(self) -> dict[str, str]:
        return {
            "SITE_ID": self.site.id,
            "SITE_NAME": self.site.name,
            "REGION": self.site.region,
            "NETWORK_ZONE": self.site.network_zone,
            "DEPLOYMENT_MODE": self.deployment_mode,
            "RUNTIME_MODE": self.runtime.mode,
            "REDPANDA_BROKERS": self.runtime.redpanda_brokers,
            "HISTORIAN_BACKEND": self.runtime.historian_backend,
            "LLM_PROVIDER": self.runtime.ai.provider,
            "LLM_ENDPOINT_URL": self.runtime.ai.endpoint_url,
            "LLM_MODEL_ID": self.runtime.ai.model_id,
            "LLM_LOCAL_ONLY": "true" if self.runtime.ai.local_only else "false",
            "DATASTREAM_BACKUP_DIR": self.backups.directory,
            "DATASTREAM_BACKUP_SCHEDULE": self.backups.schedule,
            "DATASTREAM_BACKUP_RETENTION_DAYS": str(self.backups.retention_days),
            "DATASTREAM_FEDERATION_ENABLED": "true" if self.federation.enabled else "false",
            "DATASTREAM_FEDERATION_EXPORT_MODE": self.federation.export_mode,
            "DATASTREAM_CENTRAL_ENDPOINT": self.federation.central_endpoint or "",
        }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_site_profile(path: Path | str) -> SiteProfile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    site = data.get("site") or {}
    runtime = data.get("runtime") or {}
    ai = runtime.get("ai") or {}
    backups = data.get("backups") or {}
    federation = data.get("federation") or {}

    deployment_mode = str(data.get("deployment_mode", "")).strip()
    default_runtime_mode = {
        "single-site": "python-fallback",
        "plant-local": "flink-local",
        "federated": "flink-production",
    }.get(deployment_mode, "python-fallback")
    return SiteProfile(
        schema_version=int(data.get("schema_version", 1)),
        profile_id=str(data.get("profile_id", "")).strip(),
        deployment_mode=deployment_mode,
        site=SiteIdentity(
            id=str(site.get("id", "")).strip(),
            name=str(site.get("name", "")).strip(),
            region=str(site.get("region", "")).strip(),
            network_zone=str(site.get("network_zone", "")).strip(),
        ),
        runtime=RuntimeProfile(
            image_tag=str(runtime.get("image_tag", "latest")).strip(),
            mode=str(runtime.get("mode", default_runtime_mode)).strip() or default_runtime_mode,
            redpanda_brokers=str(runtime.get("redpanda_brokers", "")).strip(),
            historian_backend=str(runtime.get("historian_backend", "timescaledb")).strip(),
            ai=AIBackendProfile(
                provider=str(ai.get("provider", "openai_compat")).strip(),
                endpoint_url=str(ai.get("endpoint_url", "")).strip(),
                model_id=str(ai.get("model_id", "")).strip(),
                local_only=_as_bool(ai.get("local_only", False)),
            ),
        ),
        backups=BackupPolicy(
            directory=str(backups.get("directory", "backups")).strip(),
            schedule=str(backups.get("schedule", "daily")).strip(),
            retention_days=int(backups.get("retention_days", 7)),
            restore_test_database=str(backups.get("restore_test_database")).strip() if backups.get("restore_test_database") else None,
        ),
        federation=FederationProfile(
            enabled=_as_bool(federation.get("enabled", False)),
            export_mode=str(federation.get("export_mode", "none")).strip(),
            central_endpoint=str(federation.get("central_endpoint")).strip() if federation.get("central_endpoint") else None,
        ),
    )


def validate_site_profile(profile: SiteProfile) -> list[str]:
    errors: list[str] = []

    if profile.schema_version != 1:
        errors.append(f"unsupported schema_version: {profile.schema_version}")
    if not profile.profile_id:
        errors.append("profile_id is required")
    if profile.deployment_mode not in VALID_DEPLOYMENT_MODES:
        errors.append(f"deployment_mode must be one of {sorted(VALID_DEPLOYMENT_MODES)}")
    if profile.runtime.mode not in VALID_RUNTIME_MODES:
        errors.append(f"runtime.mode must be one of {sorted(VALID_RUNTIME_MODES)}")
    if not profile.site.id:
        errors.append("site.id is required")
    if not profile.site.name:
        errors.append("site.name is required")
    if not profile.runtime.redpanda_brokers:
        errors.append("runtime.redpanda_brokers is required")
    if not profile.runtime.historian_backend:
        errors.append("runtime.historian_backend is required")
    if profile.runtime.ai.provider != "disabled" and not profile.runtime.ai.endpoint_url:
        errors.append("runtime.ai.endpoint_url is required unless the provider is disabled")
    if profile.runtime.ai.provider != "disabled" and not profile.runtime.ai.model_id:
        errors.append("runtime.ai.model_id is required unless the provider is disabled")
    if not profile.backups.directory:
        errors.append("backups.directory is required")
    if not profile.backups.schedule:
        errors.append("backups.schedule is required")
    if profile.backups.retention_days < 1:
        errors.append("backups.retention_days must be >= 1")
    if profile.deployment_mode == "federated" and not profile.federation.enabled:
        errors.append("federation.enabled must be true for deployment_mode=federated")
    if profile.federation.enabled and not profile.federation.central_endpoint:
        errors.append("federation.central_endpoint is required when federation.enabled=true")
    if not profile.federation.enabled and profile.federation.export_mode not in {"none", ""}:
        errors.append("federation.export_mode must be 'none' when federation is disabled")

    return errors
