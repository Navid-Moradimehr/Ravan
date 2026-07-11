from __future__ import annotations

import asyncio


def test_federation_metadata_endpoint_is_non_secret_and_valid():
    from services.api_service.routers.metadata import federation_metadata

    payload = asyncio.run(federation_metadata("config/project-manifest.yaml"))
    assert payload["valid"] is True
    assert payload["organization_id"] == "demo-industrial-fleet"
    assert payload["sites"] == ["demo-site", "plant-a"]
    assert "central_cluster" in payload["federation"]
    assert "password" not in str(payload).lower()
