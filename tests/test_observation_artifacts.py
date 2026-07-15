from __future__ import annotations

import pytest

from services.common.model_data_contract import ObservationArtifactReference


def test_artifact_reference_accepts_object_store_uri_and_normalizes_checksum():
    reference = ObservationArtifactReference(
        artifact_id="camera-1-0001",
        site_id="plant-a",
        source_id="camera-1",
        modality="image",
        uri="s3://lakehouse/plant-a/camera-1/0001.jpg",
        sha256="A" * 64,
    )
    assert reference.sha256 == "a" * 64


def test_artifact_reference_rejects_local_path_without_file_scheme():
    with pytest.raises(ValueError, match="allowed s3:// or file:// scheme"):
        ObservationArtifactReference(
            artifact_id="a-1",
            site_id="plant-a",
            source_id="camera-1",
            modality="image",
            uri="C:/captures/0001.jpg",
        )
