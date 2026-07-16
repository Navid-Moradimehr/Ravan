from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from services.edge_ingest.connectors.opcua import opcua_quality, read_opcua_sample


class _Status:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def is_good(self) -> bool: return self.kind == "good"
    def is_bad(self) -> bool: return self.kind == "bad"
    def __str__(self) -> str: return self.kind


def test_opcua_quality_preserves_bad_and_uncertain_status():
    assert opcua_quality(_Status("good")) == "good"
    assert opcua_quality(_Status("bad")) == "bad"
    assert opcua_quality(_Status("uncertain")) == "uncertain"


def test_opcua_sample_preserves_server_timestamp_and_value():
    source_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class Node:
        async def read_data_value(self):
            return SimpleNamespace(
                Value=SimpleNamespace(Value=42.5),
                StatusCode=_Status("uncertain"),
                SourceTimestamp=source_time,
            )

    value, quality, timestamp = asyncio.run(read_opcua_sample(Node()))
    assert value == 42.5
    assert quality == "uncertain"
    assert timestamp == source_time.isoformat()
