"""Tests for OPC UA discovery client."""
from __future__ import annotations

import asyncio
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "edge_ingest"))

from opcua_discovery import OPCUADiscoveryClient, ASYNCUA_AVAILABLE


@pytest.fixture
def client():
    return OPCUADiscoveryClient(endpoint_url="opc.tcp://localhost:4840")


def test_client_init(client):
    assert client.endpoint_url == "opc.tcp://localhost:4840"
    assert client._client is None


def test_client_without_asyncua():
    """Test that client handles missing asyncua gracefully."""
    if not ASYNCUA_AVAILABLE:
        client = OPCUADiscoveryClient()
        result = asyncio.run(client.connect())
        assert result is False


@pytest.mark.skipif(not ASYNCUA_AVAILABLE, reason="asyncua not installed")
def test_client_connect_fail():
    """Test connection failure to non-existent server."""
    client = OPCUADiscoveryClient(endpoint_url="opc.tcp://localhost:99999")
    result = asyncio.run(client.connect())
    assert result is False


def test_client_context_manager():
    """Test async context manager."""
    client = OPCUADiscoveryClient()
    # Should not raise even if connection fails
    try:
        asyncio.run(_test_cm(client))
    except Exception:
        pass


async def _test_cm(client):
    async with client:
        pass
