"""Tests for edge-to-cloud federation and batch ingest."""
from __future__ import annotations

import pytest


def test_federation_loop_disabled_without_cloud_url(monkeypatch):
    from services.federation import main as fed

    monkeypatch.setattr(fed, "CLOUD_HISTORIAN_URL", "")
    # Should return immediately without error.
    import asyncio
    asyncio.run(fed.federation_loop())


def test_batch_ingest_endpoint_exists():
    import services.api_service.main as api_main

    routes = {r.path for r in api_main.app.routes}
    assert "/api/v1/events/ingest/batch" in routes


def test_batch_ingest_empty_records():
    import asyncio
    import services.api_service.main as api_main

    async def call():
        return await api_main.ingest_batch({"table": "industrial_events", "records": []})

    result = asyncio.run(call())
    assert result["inserted"] == 0
    assert result["table"] == "industrial_events"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
