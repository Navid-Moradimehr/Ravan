from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.common.asset_registry import build_asset_registry_snapshot
from services.common.event_catalog import build_event_catalog_snapshot
from services.common.governance_plane import build_governance_snapshot
from services.common.lineage_contract import build_lineage_snapshot
from services.common.metadata_plane import build_metadata_plane_snapshot


DEFAULT_METADATA_ARTIFACT_DIR = Path("data/metadata")


@dataclass(frozen=True)
class MetadataArtifactBundle:
    generated_at: str
    metadata_plane: dict[str, Any]
    governance: dict[str, Any]
    asset_registry: dict[str, Any]
    event_catalog: dict[str, Any]
    lineage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "metadata_plane": self.metadata_plane,
            "governance": self.governance,
            "asset_registry": self.asset_registry,
            "event_catalog": self.event_catalog,
            "lineage": self.lineage,
        }


def build_metadata_artifact_bundle(
    *,
    site_profile_path: Path | str | None = None,
    asset_config: Path | str = Path("config/assets.yaml"),
    project_manifest_path: Path | str = Path("config/project-manifest.yaml"),
    semantic_store_path: Path | str | None = None,
    site_id: str | None = None,
) -> MetadataArtifactBundle:
    metadata_plane = build_metadata_plane_snapshot(
        site_profile_path=site_profile_path,
        asset_config=asset_config,
        semantic_store_path=semantic_store_path,
    )
    governance = build_governance_snapshot()
    asset_registry = build_asset_registry_snapshot(asset_config=asset_config, site_id=site_id)
    event_catalog = build_event_catalog_snapshot(project_manifest_path=project_manifest_path)
    lineage = build_lineage_snapshot(site_id=site_id)
    return MetadataArtifactBundle(
        generated_at=datetime.now(timezone.utc).isoformat(),
        metadata_plane=metadata_plane,
        governance=governance,
        asset_registry=asset_registry,
        event_catalog=event_catalog,
        lineage=lineage,
    )


def write_metadata_artifact_bundle(
    report_dir: Path | str,
    bundle: MetadataArtifactBundle,
) -> list[Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    files = {
        "metadata-plane.json": bundle.metadata_plane,
        "governance.json": bundle.governance,
        "asset-registry.json": bundle.asset_registry,
        "event-catalog.json": bundle.event_catalog,
        "lineage.json": bundle.lineage,
        "metadata-artifacts-summary.json": bundle.to_dict(),
    }
    for filename, payload in files.items():
        path = output_dir / filename
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        written.append(path)
    return written
