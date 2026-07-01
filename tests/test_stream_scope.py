from __future__ import annotations

from services.common.stream_scope import correlation_group_key, derive_stream_scope, stream_partition_key


def test_stream_partition_key_includes_source_identity():
    first = {
        "site": "plant-a",
        "line": "line-01",
        "source_protocol": "opcua",
        "source_id": "plc-1/node-7",
        "asset_id": "pump-01",
        "tag": "temperature",
    }
    second = {
        "site": "plant-a",
        "line": "line-01",
        "source_protocol": "opcua",
        "source_id": "plc-2/node-7",
        "asset_id": "pump-01",
        "tag": "temperature",
    }

    assert stream_partition_key(first) != stream_partition_key(second)
    assert correlation_group_key(first) == correlation_group_key(second)


def test_derive_stream_scope_falls_back_safely():
    scope = derive_stream_scope({"asset_id": "pump-01", "tag": "pressure"})
    assert scope.site == "demo-site"
    assert scope.asset_id == "pump-01"
    assert scope.tag == "pressure"

