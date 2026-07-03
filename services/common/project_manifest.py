from __future__ import annotations

import hashlib
import json
import hmac
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from services.common.site_profiles import load_site_profile, validate_site_profile


VALID_BRIDGE_MODES = {"replicate", "fanout", "correlate", "rollup"}
VALID_EXPORT_LAYOUTS = {"flat", "systemd", "windows", "kubernetes", "package"}
VALID_EXPORT_FORMATS = {"env", "yaml", "both"}


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

    def source_site_map(self) -> dict[str, str]:
        return {source.source_id: source.site_id for source in self.sources if source.site_id}

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

    def bundle_for_site(self, site_id: str | None = None) -> dict[str, Any]:
        envs = self.to_site_envs()
        if site_id:
            if site_id not in envs:
                raise ValueError(f"site_id not found in manifest: {site_id}")
            return {
                "project_id": self.project_id,
                "name": self.name,
                "site_id": site_id,
                "site_profile": str(self.site_profile_paths()[site_id]),
                "env": envs[site_id],
            }
        return {
            "project_id": self.project_id,
            "name": self.name,
            "sites": [
                {
                    "site_id": sid,
                    "site_profile": str(self.site_profile_paths()[sid]),
                    "env": env,
                }
                for sid, env in envs.items()
            ],
        }

    def _site_bundle(self, site_id: str, env: dict[str, str]) -> dict[str, Any]:
        source_dicts = [source.to_dict() for source in self.sources if source.site_id == site_id]
        return {
            "project_id": self.project_id,
            "project_name": self.name,
            "site_id": site_id,
            "site_profile": str(self.site_profile_paths()[site_id]),
            "env": env,
            "sources": source_dicts,
            "bridge_rules": [rule.to_dict() for rule in self.bridge_rules],
            "correlation_groups": [group.to_dict() for group in self.correlation_groups],
            "retention": self.retention.to_dict(),
        }

    @staticmethod
    def _render_env(env: dict[str, str]) -> str:
        return "\n".join(f"{key}={value}" for key, value in sorted(env.items())) + "\n"

    @staticmethod
    def _write_text(path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _render_site_profile_yaml(self, site_id: str) -> str:
        profile = load_site_profile(self.site_profile_paths()[site_id])
        return yaml.safe_dump(profile.to_dict(), sort_keys=False, allow_unicode=True)

    def _render_bundle_yaml(self, site_id: str, env: dict[str, str]) -> str:
        return yaml.safe_dump(self._site_bundle(site_id, env), sort_keys=False, allow_unicode=True)

    def _render_systemd_unit(self, site_id: str) -> str:
        site_root = f"/etc/datastream/{self.project_id}/{site_id}"
        return "\n".join(
            [
                "[Unit]",
                f"Description=Data Stream runtime for {self.name} ({site_id})",
                "After=network-online.target",
                "Wants=network-online.target",
                "",
                "[Service]",
                "Type=simple",
                "Restart=always",
                "RestartSec=5",
                f"EnvironmentFile={site_root}/env/site.env",
                f"WorkingDirectory={site_root}",
                f"ExecStart=/usr/bin/env datastreamd up --site-profile {site_root}/site-profile.yaml",
                "",
                "[Install]",
                "WantedBy=multi-user.target",
                "",
            ]
        )

    def _render_systemd_readme(self, site_id: str) -> str:
        return "\n".join(
            [
                f"# {self.name} - {site_id}",
                "",
                "This directory is ready to be copied to /etc/datastream/<project>/<site>.",
                "",
                "Install steps:",
                "1. Copy the exported site directory to /etc/datastream/<project>/<site>.",
                "2. Run systemd/install.sh on the target host as root or with sudo.",
                "3. Reload systemd and enable the unit.",
                "",
                "Secrets and external credentials are intentionally left to the operator to provide.",
                "",
            ]
        )

    def _render_systemd_install(self, site_id: str) -> str:
        unit_name = f"datastreamd-{site_id}.service"
        return "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                'SOURCE_DIR="${1:-$(pwd)}"',
                'TARGET_DIR="${2:-/etc/datastream/' + f"{self.project_id}/{site_id}" + '}"',
                'UNIT_NAME="${3:-' + unit_name + '}"',
                'SERVICE_FILE="${4:-/etc/systemd/system/${UNIT_NAME}}"',
                "",
                'install -d -m 0755 "${TARGET_DIR}"',
                'install -d -m 0755 "${TARGET_DIR}/env"',
                'install -d -m 0755 "${TARGET_DIR}/systemd"',
                'install -m 0644 "${SOURCE_DIR}/site-profile.yaml" "${TARGET_DIR}/site-profile.yaml"',
                'install -m 0644 "${SOURCE_DIR}/bundle.yaml" "${TARGET_DIR}/bundle.yaml"',
                'install -m 0644 "${SOURCE_DIR}/env/site.env" "${TARGET_DIR}/env/site.env"',
                'install -m 0644 "${SOURCE_DIR}/systemd/datastreamd.service" "${SERVICE_FILE}"',
                "systemctl daemon-reload",
                'systemctl enable "${UNIT_NAME}"',
                'echo "Installed ${UNIT_NAME} using ${TARGET_DIR}"',
                "",
            ]
        )

    def _render_systemd_uninstall(self, site_id: str) -> str:
        unit_name = f"datastreamd-{site_id}.service"
        return "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                'UNIT_NAME="${1:-' + unit_name + '}"',
                'systemctl disable "${UNIT_NAME}" || true',
                'rm -f "/etc/systemd/system/${UNIT_NAME}"',
                'rm -rf "/etc/datastream/' + f"{self.project_id}/{site_id}" + '"',
                "systemctl daemon-reload",
                'echo "Removed ${UNIT_NAME}"',
                "",
            ]
        )

    def _render_windows_readme(self, site_id: str) -> str:
        return "\n".join(
            [
                f"# {self.name} - {site_id}",
                "",
                "This directory is ready to be copied to a native Windows host.",
                "",
                "Install steps:",
                "1. Copy the exported site directory to the target host.",
                "2. Run windows/install.ps1 as Administrator.",
                "3. Review the generated service command and adjust the Python runtime path if your installer bundles a private runtime.",
                "4. Start the datastreamd service and verify datastreamctl status.",
                "",
                "WSL2 is intentionally not required for production installs.",
                "",
            ]
        )

    def _render_windows_cmd(self, command: str, extra_args: str = "") -> str:
        return "\n".join(
            [
                "@echo off",
                "setlocal",
                "set PYTHON=python",
                f'"%PYTHON%" -m {command} {extra_args} %*',
                "endlocal",
                "",
            ]
        )

    def _render_windows_install(self, site_id: str) -> str:
        target_root = f"C:\\Datastream\\{self.project_id}\\{site_id}"
        service_name = f"datastreamd-{site_id}"
        return "\n".join(
            [
                "param(",
                "    [string]$SourceDir = $PSScriptRoot,",
                f"    [string]$TargetDir = '{target_root}',",
                f"    [string]$ServiceName = '{service_name}'",
                ")",
                "",
                "$ErrorActionPreference = 'Stop'",
                "",
                "$binDir = Join-Path $TargetDir 'bin'",
                "$configDir = Join-Path $TargetDir 'config'",
                "$dataDir = Join-Path $TargetDir 'data'",
                "$logsDir = Join-Path $TargetDir 'logs'",
                "$modelsDir = Join-Path $TargetDir 'models'",
                "$backupsDir = Join-Path $TargetDir 'backups'",
                "$envDir = Join-Path $TargetDir 'env'",
                "",
                "New-Item -ItemType Directory -Force -Path $binDir, $configDir, $dataDir, $logsDir, $modelsDir, $backupsDir, $envDir | Out-Null",
                "Copy-Item (Join-Path $SourceDir 'site-profile.yaml') (Join-Path $TargetDir 'site-profile.yaml') -Force",
                "Copy-Item (Join-Path $SourceDir 'bundle.yaml') (Join-Path $TargetDir 'bundle.yaml') -Force",
                "Copy-Item (Join-Path $SourceDir 'env\\site.env') (Join-Path $envDir 'site.env') -Force",
                "",
                "$ctlWrapper = @'",
                self._render_windows_cmd("services.cli.datastreamctl"),
                "'@",
                "Set-Content -Path (Join-Path $binDir 'datastreamctl.cmd') -Value $ctlWrapper -Encoding ASCII",
                "",
                "$dWrapper = @'",
                self._render_windows_cmd("services.cli.datastreamd", "up --site-profile \"%~dp0..\\site-profile.yaml\""),
                "'@",
                "Set-Content -Path (Join-Path $binDir 'datastreamd.cmd') -Value $dWrapper -Encoding ASCII",
                "",
                "$pythonExe = (Get-Command python -ErrorAction Stop).Source",
                "$binaryPath = '\"' + $pythonExe + '\" -m services.cli.datastreamd up --site-profile \"' + (Join-Path $TargetDir 'site-profile.yaml') + '\"'",
                "if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {",
                "    Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue",
                "    sc.exe delete $ServiceName | Out-Null",
                "}",
                "New-Service -Name $ServiceName -BinaryPathName $binaryPath -DisplayName $ServiceName -Description 'Local Stream Engine runtime' -StartupType Automatic | Out-Null",
                "Write-Host ('Installed ' + $ServiceName + ' into ' + $TargetDir)",
                "",
            ]
        )

    def _render_windows_uninstall(self, site_id: str) -> str:
        service_name = f"datastreamd-{site_id}"
        return "\n".join(
            [
                "param(",
                f"    [string]$ServiceName = '{service_name}',",
                f"    [string]$TargetDir = 'C:\\Datastream\\{self.project_id}\\{site_id}'",
                ")",
                "",
                "$ErrorActionPreference = 'Stop'",
                "",
                "if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {",
                "    Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue",
                "    sc.exe delete $ServiceName | Out-Null",
                "}",
                "Write-Host ('Removed ' + $ServiceName + '. Site files remain in ' + $TargetDir + ' for rollback unless you delete them manually.')",
                "",
            ]
        )

    def _render_kubernetes_configmap(self, site_id: str, env: dict[str, str]) -> str:
        payload = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"datastream-{site_id}-config",
                "labels": {
                    "app.kubernetes.io/name": "datastream",
                    "app.kubernetes.io/instance": site_id,
                    "datastream/project": self.project_id,
                },
            },
            "data": env,
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    def _render_kubernetes_site_profile_configmap(self, site_id: str) -> str:
        profile = load_site_profile(self.site_profile_paths()[site_id])
        payload = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"datastream-{site_id}-site-profile",
                "labels": {
                    "app.kubernetes.io/name": "datastream",
                    "app.kubernetes.io/instance": site_id,
                    "datastream/project": self.project_id,
                },
            },
            "data": {
                "site-profile.yaml": yaml.safe_dump(profile.to_dict(), sort_keys=False, allow_unicode=True),
            },
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    def _render_kubernetes_deployment(self, site_id: str) -> str:
        payload = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"datastream-{site_id}",
                "labels": {
                    "app.kubernetes.io/name": "datastream",
                    "app.kubernetes.io/instance": site_id,
                    "datastream/project": self.project_id,
                },
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": "datastream",
                        "app.kubernetes.io/instance": site_id,
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": "datastream",
                            "app.kubernetes.io/instance": site_id,
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "datastreamd",
                                "image": "datastream:latest",
                                "imagePullPolicy": "IfNotPresent",
                                "args": [
                                    "up",
                                    "--site-profile",
                                    "/etc/datastream/site-profile.yaml",
                                ],
                                "envFrom": [
                                    {"configMapRef": {"name": f"datastream-{site_id}-config"}},
                                ],
                                "volumeMounts": [
                                    {
                                        "name": "site-profile",
                                        "mountPath": "/etc/datastream/site-profile.yaml",
                                        "subPath": "site-profile.yaml",
                                        "readOnly": True,
                                    }
                                ],
                                "ports": [{"containerPort": 8080, "name": "http"}],
                                "resources": {
                                    "requests": {"cpu": "250m", "memory": "512Mi"},
                                    "limits": {"cpu": "1000m", "memory": "1Gi"},
                                },
                            }
                        ],
                        "volumes": [
                            {
                                "name": "site-profile",
                                "configMap": {"name": f"datastream-{site_id}-site-profile"},
                            }
                        ],
                    },
                },
            },
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    def _render_kubernetes_service(self, site_id: str) -> str:
        payload = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"datastream-{site_id}",
                "labels": {
                    "app.kubernetes.io/name": "datastream",
                    "app.kubernetes.io/instance": site_id,
                    "datastream/project": self.project_id,
                },
            },
            "spec": {
                "type": "ClusterIP",
                "selector": {
                    "app.kubernetes.io/name": "datastream",
                    "app.kubernetes.io/instance": site_id,
                },
                "ports": [{"name": "http", "port": 8080, "targetPort": "http"}],
            },
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    def _render_kubernetes_readme(self, site_id: str) -> str:
        return "\n".join(
            [
                f"# {self.name} - {site_id}",
                "",
                "This directory contains a Kubernetes starter bundle.",
                "",
                "Run `kubectl apply -k .` after replacing the image tag with your release build.",
                "",
                "Secrets are intentionally not bundled. Provide broker credentials, external APIs, and model endpoints via your cluster secret workflow.",
                "",
            ]
        )

    def _render_kubernetes_helm_values(self, site_id: str, env: dict[str, str]) -> str:
        profile = load_site_profile(self.site_profile_paths()[site_id])
        runtime_mode = profile.runtime.mode
        processor_enabled = runtime_mode == "python-fallback"
        flink_job_enabled = runtime_mode in {"flink-local", "flink-production"}
        payload = {
            "fullnameOverride": f"datastream-{site_id}",
            "namespaceOverride": f"datastream-{site_id}",
            "image": {
                "repository": "data-stream",
                "tag": profile.runtime.image_tag,
                "pullPolicy": "IfNotPresent",
            },
            "processor": {
                "enabled": processor_enabled,
                "replicaCount": 1,
            },
            "flinkJob": {
                "enabled": flink_job_enabled,
                "replicaCount": 1,
            },
            "env": env,
            "secrets": {
                "create": False,
                "existingSecret": "data-stream-secrets",
                "data": {
                    "TIMESCALE_PASSWORD": "",
                    "JWT_SECRET": "",
                    "LLM_API_KEY": "",
                },
            },
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    def _render_kubernetes_helm_readme(self, site_id: str) -> str:
        return "\n".join(
            [
                f"# Helm overlay for {self.name} - {site_id}",
                "",
                "Use this overlay with the chart in `k8s/helm`.",
                "",
                "Example:",
                "  helm upgrade --install datastream-demo-site ./k8s/helm --namespace datastream-demo-site -f kubernetes/helm/values.generated.yaml",
                "",
                "Run `kubernetes/helm/install.sh` to use the generated release and namespace defaults.",
                "",
                "Replace the generated image tag and provide secrets through your cluster secret workflow.",
                "",
            ]
        )

    def _render_kubernetes_helm_install(self, site_id: str) -> str:
        release = f"datastream-{site_id}"
        namespace = f"datastream-{site_id}"
        return "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                'ROOT_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"',
                f'RELEASE_NAME="${{2:-{release}}}"',
                f'NAMESPACE="${{3:-{namespace}}}"',
                'VALUES_FILE="${4:-${ROOT_DIR}/values.generated.yaml}"',
                "",
                'helm upgrade --install "${RELEASE_NAME}" ./k8s/helm --namespace "${NAMESPACE}" -f "${VALUES_FILE}"',
                "",
            ]
        )

    def _render_kubernetes_kustomization(self, site_id: str) -> str:
        payload = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "namespace": "datastream",
            "resources": [
                "configmap.yaml",
                "site-profile-configmap.yaml",
                "deployment.yaml",
                "service.yaml",
            ],
            "commonLabels": {
                "app.kubernetes.io/name": "datastream",
                "app.kubernetes.io/instance": site_id,
                "datastream/project": self.project_id,
            },
        }
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)

    def _export_flat_site(self, base_dir: Path, site_id: str, env: dict[str, str], *, fmt: str, written: list[Path]) -> None:
        bundle_base = base_dir / site_id
        if fmt in {"env", "both"}:
            written.append(self._write_text(bundle_base.with_suffix(".env"), self._render_env(env)))
        if fmt in {"yaml", "both"}:
            written.append(self._write_text(bundle_base.with_suffix(".yaml"), self._render_bundle_yaml(site_id, env)))

    def _export_structured_site(self, base_dir: Path, site_id: str, env: dict[str, str], *, fmt: str, layout: str, written: list[Path]) -> None:
        site_root = base_dir / site_id
        site_profile_path = site_root / "site-profile.yaml"
        bundle_path = site_root / "bundle.yaml"
        env_path = site_root / "env" / "site.env"
        written.append(self._write_text(site_profile_path, self._render_site_profile_yaml(site_id)))
        written.append(self._write_text(bundle_path, self._render_bundle_yaml(site_id, env)))
        if fmt in {"env", "both"}:
            written.append(self._write_text(env_path, self._render_env(env)))
        if layout == "systemd":
            written.append(self._write_text(site_root / "systemd" / "datastreamd.service", self._render_systemd_unit(site_id)))
            written.append(self._write_text(site_root / "systemd" / "README.md", self._render_systemd_readme(site_id)))
            written.append(self._write_text(site_root / "systemd" / "install.sh", self._render_systemd_install(site_id)))
            written.append(self._write_text(site_root / "systemd" / "uninstall.sh", self._render_systemd_uninstall(site_id)))
        elif layout == "windows":
            written.append(self._write_text(site_root / "windows" / "README.md", self._render_windows_readme(site_id)))
            written.append(self._write_text(site_root / "windows" / "install.ps1", self._render_windows_install(site_id)))
            written.append(self._write_text(site_root / "windows" / "uninstall.ps1", self._render_windows_uninstall(site_id)))
            written.append(self._write_text(site_root / "windows" / "bin" / "datastreamctl.cmd", self._render_windows_cmd("services.cli.datastreamctl")))
            written.append(self._write_text(site_root / "windows" / "bin" / "datastreamd.cmd", self._render_windows_cmd("services.cli.datastreamd", "up")))
        elif layout == "kubernetes":
            written.append(self._write_text(site_root / "kubernetes" / "configmap.yaml", self._render_kubernetes_configmap(site_id, env)))
            written.append(self._write_text(site_root / "kubernetes" / "site-profile-configmap.yaml", self._render_kubernetes_site_profile_configmap(site_id)))
            written.append(self._write_text(site_root / "kubernetes" / "deployment.yaml", self._render_kubernetes_deployment(site_id)))
            written.append(self._write_text(site_root / "kubernetes" / "service.yaml", self._render_kubernetes_service(site_id)))
            written.append(self._write_text(site_root / "kubernetes" / "kustomization.yaml", self._render_kubernetes_kustomization(site_id)))
            written.append(self._write_text(site_root / "kubernetes" / "README.md", self._render_kubernetes_readme(site_id)))
            written.append(self._write_text(site_root / "kubernetes" / "helm" / "values.generated.yaml", self._render_kubernetes_helm_values(site_id, env)))
            written.append(self._write_text(site_root / "kubernetes" / "helm" / "README.md", self._render_kubernetes_helm_readme(site_id)))
            written.append(self._write_text(site_root / "kubernetes" / "helm" / "install.sh", self._render_kubernetes_helm_install(site_id)))

    def _render_package_readme(self, site_id: str) -> str:
        return "\n".join(
            [
                f"# Deployment package for {self.name} - {site_id}",
                "",
                "This directory contains all deployable outputs for one site:",
                "",
                "- `flat/` for quick inspection or CI artifacts",
                "- `systemd/` for host-based installation",
                "- `kubernetes/` for kustomize and Helm-based deployment",
                "",
                "The generated Helm wrapper uses site-specific release and namespace defaults.",
                "",
            ]
        )

    def _export_package_site(self, base_dir: Path, site_id: str, env: dict[str, str], *, fmt: str, written: list[Path]) -> None:
        site_root = base_dir / site_id
        written.append(self._write_text(site_root / "README.md", self._render_package_readme(site_id)))
        if fmt in {"env", "both"}:
            written.append(self._write_text(site_root / "flat" / "site.env", self._render_env(env)))
        if fmt in {"yaml", "both"}:
            written.append(self._write_text(site_root / "flat" / "bundle.yaml", self._render_bundle_yaml(site_id, env)))
        written.append(self._write_text(site_root / "site-profile.yaml", self._render_site_profile_yaml(site_id)))
        written.append(self._write_text(site_root / "bundle.yaml", self._render_bundle_yaml(site_id, env)))
        written.append(self._write_text(site_root / "env" / "site.env", self._render_env(env)))
        written.append(self._write_text(site_root / "systemd" / "datastreamd.service", self._render_systemd_unit(site_id)))
        written.append(self._write_text(site_root / "systemd" / "README.md", self._render_systemd_readme(site_id)))
        written.append(self._write_text(site_root / "systemd" / "install.sh", self._render_systemd_install(site_id)))
        written.append(self._write_text(site_root / "systemd" / "uninstall.sh", self._render_systemd_uninstall(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "configmap.yaml", self._render_kubernetes_configmap(site_id, env)))
        written.append(self._write_text(site_root / "kubernetes" / "site-profile-configmap.yaml", self._render_kubernetes_site_profile_configmap(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "deployment.yaml", self._render_kubernetes_deployment(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "service.yaml", self._render_kubernetes_service(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "kustomization.yaml", self._render_kubernetes_kustomization(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "README.md", self._render_kubernetes_readme(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "helm" / "values.generated.yaml", self._render_kubernetes_helm_values(site_id, env)))
        written.append(self._write_text(site_root / "kubernetes" / "helm" / "README.md", self._render_kubernetes_helm_readme(site_id)))
        written.append(self._write_text(site_root / "kubernetes" / "helm" / "install.sh", self._render_kubernetes_helm_install(site_id)))

    def lint(self) -> list[str]:
        issues = validate_project_manifest(self)
        site_ids = {site.site_id for site in self.sites}
        source_site_map = self.source_site_map()
        topic_to_sources: dict[str, list[str]] = {}
        bridge_signatures: set[tuple[str, str, tuple[str, ...], tuple[str, ...], str]] = set()

        for source in self.sources:
            if source.topic:
                topic_to_sources.setdefault(source.topic, []).append(source.source_id)

        for topic, source_ids in topic_to_sources.items():
            if len(source_ids) > 1:
                issues.append(f"topic collision: {topic} used by {source_ids}")

        for rule in self.bridge_rules:
            signature = (rule.mode, rule.name, rule.from_sources, rule.to_sources, rule.topic_template)
            if signature in bridge_signatures:
                issues.append(f"duplicate bridge rule signature: {rule.name}")
            bridge_signatures.add(signature)

        for group in self.correlation_groups:
            if len(set(group.members)) != len(group.members):
                issues.append(f"correlation group {group.name}: duplicate member entries")
            if len(group.members) > 1 and group.strategy == "site_asset_tag":
                grouped_sites = {source_site_map.get(member, "") for member in group.members if source_site_map.get(member, "")}
                if len(grouped_sites) > 1:
                    issues.append(f"correlation group {group.name}: spans multiple sites {sorted(grouped_sites)}")

        for source in self.sources:
            if source.site_id and source.site_id not in site_ids:
                issues.append(f"source {source.source_id}: site_id {source.site_id} not defined in sites")

        for site in self.sites:
            profile = load_site_profile(site.profile_path)
            if profile.backups.retention_days != self.retention.backup_days:
                issues.append(
                    f"retention mismatch for {site.site_id}: site backups.retention_days={profile.backups.retention_days} "
                    f"project retention.backup_days={self.retention.backup_days}"
                )
        return issues

    def export_bundles(
        self,
        output_dir: Path | str,
        *,
        site_id: str | None = None,
        fmt: str = "both",
        layout: str = "flat",
    ) -> list[Path]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        if fmt not in VALID_EXPORT_FORMATS:
            raise ValueError(f"invalid export format: {fmt}")
        if layout not in VALID_EXPORT_LAYOUTS:
            raise ValueError(f"invalid export layout: {layout}")
        envs = self.to_site_envs()
        targets = [site_id] if site_id else list(envs.keys())
        written: list[Path] = []

        for sid in targets:
            if sid not in envs:
                raise ValueError(f"site_id not found in manifest: {sid}")
            env = envs[sid]
            if layout == "flat":
                self._export_flat_site(output_path, sid, env, fmt=fmt, written=written)
            elif layout in {"systemd", "windows", "kubernetes"}:
                self._export_structured_site(output_path, sid, env, fmt=fmt, layout=layout, written=written)
            else:
                self._export_package_site(output_path, sid, env, fmt=fmt, written=written)
        return written

    def export_release_artifact(
        self,
        output_dir: Path | str,
        *,
        site_id: str,
        fmt: str = "both",
        signing_key: str | None = None,
        signing_key_id: str = "operator-provided",
    ) -> list[Path]:
        output_path = Path(output_dir)
        written = self.export_package(output_path, site_id=site_id, fmt=fmt)
        site_root = output_path / site_id
        package_files = [path for path in site_root.rglob("*") if path.is_file()]
        checksums = []
        for path in sorted(package_files):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            checksums.append(f"{digest}  {path.relative_to(site_root).as_posix()}")
        payload = {
            "project_id": self.project_id,
            "project_name": self.name,
            "site_id": site_id,
            "artifact_type": "release-package",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "format": fmt,
            "layout": "package",
            "file_count": len(package_files),
            "checksums_file": "checksums.sha256",
            "release_notes": [
                "This is a self-hosted release skeleton.",
                "Secrets, signing keys, and installer signing remain operator-owned.",
                "Use the generated checksums file with your downstream signing workflow.",
            ],
        }
        written.append(
            self._write_text(
                site_root / "release-manifest.json",
                json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False),
            )
        )
        written.append(self._write_text(site_root / "checksums.sha256", "\n".join(checksums) + "\n"))
        if signing_key:
            manifest_bytes = (site_root / "release-manifest.json").read_bytes()
            checksums_bytes = (site_root / "checksums.sha256").read_bytes()
            signature = hmac.new(
                signing_key.encode("utf-8"),
                manifest_bytes + b"\n" + checksums_bytes,
                hashlib.sha256,
            ).hexdigest()
            signature_payload = {
                "project_id": self.project_id,
                "project_name": self.name,
                "site_id": site_id,
                "artifact_type": "release-signature",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "algorithm": "HMAC-SHA256",
                "key_id": signing_key_id,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "checksums_sha256": hashlib.sha256(checksums_bytes).hexdigest(),
                "signature": signature,
            }
            written.append(
                self._write_text(
                    site_root / "release-signature.json",
                    json.dumps(signature_payload, indent=2, sort_keys=False, ensure_ascii=False),
                )
            )
        return written

    def export_package(
        self,
        output_dir: Path | str,
        *,
        site_id: str | None = None,
        fmt: str = "both",
    ) -> list[Path]:
        return self.export_bundles(output_dir, site_id=site_id, fmt=fmt, layout="package")


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
    source_site_map = manifest.source_site_map()
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
            if profile.site.id and profile.site.id != site.site_id:
                errors.append(
                    f"{site.site_id}: site profile site.id {profile.site.id} does not match manifest site_id {site.site_id}"
                )

    source_ids = {source.source_id for source in manifest.sources}
    if len(source_ids) != len(manifest.sources):
        errors.append("source_id values must be unique")
    for source in manifest.sources:
        if not source.source_id:
            errors.append("source.source_id is required")
        if not source.site_id:
            errors.append(f"source {source.source_id or '?'}: site_id is required")
        if source.site_id and source.site_id not in site_ids:
            errors.append(f"source {source.source_id}: unknown site_id {source.site_id}")
        if source.site_id and source.topic and source.site_id not in source.topic.split("/"):
            errors.append(f"source {source.source_id}: topic must include site boundary for {source.site_id}")
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
        rule_sites = {source_site_map.get(item, "") for item in (*rule.from_sources, *rule.to_sources) if source_site_map.get(item, "")}
        if len(rule_sites) > 1:
            if not rule.topic_template:
                errors.append(f"bridge rule {rule.name or '?'}: cross-site rules require topic_template")
            elif "{{site_id}}" not in rule.topic_template and "{{source_site_id}}" not in rule.topic_template:
                errors.append(
                    f"bridge rule {rule.name or '?'}: cross-site topic_template must include a site placeholder"
                )

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
        grouped_sites = {source_site_map.get(member, "") for member in group.members if source_site_map.get(member, "")}
        if len(grouped_sites) > 1 and group.strategy not in {"cross_site", "federated"}:
            errors.append(
                f"correlation group {group.name or '?'}: cross-site grouping requires explicit cross_site or federated strategy"
            )

    if manifest.retention.historian_days < manifest.retention.raw_days:
        errors.append("retention.historian_days must be >= retention.raw_days")
    if manifest.retention.raw_days < manifest.retention.compressed_days:
        errors.append("retention.raw_days must be >= retention.compressed_days")
    if manifest.retention.backup_days < 1:
        errors.append("retention.backup_days must be >= 1")
    return errors
