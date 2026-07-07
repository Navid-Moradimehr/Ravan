from __future__ import annotations

from services.common.metadata_artifacts import build_metadata_artifact_bundle, write_metadata_artifact_bundle


def test_metadata_artifact_bundle_contains_all_snapshots(tmp_path) -> None:
    bundle = build_metadata_artifact_bundle()

    assert bundle.metadata_plane["plane"] == "logical-metadata-plane"
    assert bundle.governance["read_only"] is True
    assert bundle.asset_registry["contracts"]["logical_registry"] is True
    assert bundle.event_catalog["contracts"]["logical_catalog"] is True
    assert bundle.lineage["openlineage_compatible"] is True

    written = write_metadata_artifact_bundle(tmp_path, bundle)
    filenames = {path.name for path in written}
    assert {"metadata-plane.json", "governance.json", "asset-registry.json", "event-catalog.json", "lineage.json", "metadata-artifacts-summary.json"} <= filenames
    assert (tmp_path / "metadata-plane.json").exists()
    assert (tmp_path / "governance.json").exists()

