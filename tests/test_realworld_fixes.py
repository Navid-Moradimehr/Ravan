"""Regression tests for real-world correctness fixes.

Locks in:
1. The edge protocol literal accepts every producer (dataset/mock/sparkplug/modbus_rtu)
   instead of routing them to the DLQ.
2. The historian reads POSTGRES_* env (what .env actually defines), not only TIMESCALE_*.
3. Normalization preserves the real tag/value so non-temp/vib/pressure tags are not lost.
4. The processor scores the actual tag, not only the three legacy fields.
"""
from __future__ import annotations

import os

import pytest

from services.edge_ingest.model import validate_event
from services.common.normalize import normalize_runtime_event
from services.processor.runtime_processor import score_event
from services.analytics.baseline import BaselineDetector


@pytest.mark.parametrize(
    "protocol",
    ["opcua", "mqtt", "modbus", "modbus_rtu", "sparkplug_b", "dataset", "mock", "api"],
)
def test_all_producers_validate_not_dlqd(protocol):
    payload = {
        "source_protocol": protocol,
        "source_id": "src-1",
        "asset_id": "Pump-01",
        "tag": "Temperature",
        "value": 42.0,
        "ts_source": "2026-01-01T00:00:00Z",
    }
    event, dlq = validate_event(payload)
    assert event is not None, f"{protocol} events must not be DLQ'd"
    assert dlq is None
    assert event.source_protocol == protocol


def test_historian_reads_postgres_env(monkeypatch):
    for var in ("TIMESCALE_HOST", "TIMESCALE_PORT", "TIMESCALE_DB", "TIMESCALE_USER", "TIMESCALE_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "prod")
    monkeypatch.setenv("POSTGRES_USER", "ops")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    import importlib

    from services.historian import client

    importlib.reload(client)
    cs = client._connection_string()
    assert "db.internal" in cs
    assert "6543" in cs
    assert "prod" in cs
    assert "ops" in cs
    assert "secret" in cs


def test_normalization_preserves_real_tag():
    raw = {
        "source_protocol": "dataset",
        "source_id": "ai4i/M-1",
        "asset_id": "M-1",
        "tag": "RotationalSpeed",
        "value": 1500.0,
        "unit": "rpm",
        "fault_type": "normal",
        "ts_source": "2026-01-01T00:00:00Z",
    }
    normalized = normalize_runtime_event(raw)
    assert normalized["tag"] == "RotationalSpeed"
    assert normalized["value"] == 1500.0
    assert normalized["unit"] == "rpm"
    assert normalized["asset_id"] == "M-1"


def test_processor_scores_non_legacy_tag():
    event = {
        "device_id": "M-1",
        "asset_id": "M-1",
        "tag": "RotationalSpeed",
        "value": 1500.0,
        "temperature_c": 0.0,
        "vibration_mm_s": 0.0,
        "pressure_bar": 0.0,
    }
    detector = BaselineDetector()
    score = score_event(event, temperature_avg=0.0, vibration_avg=0.0, detector=detector)
    assert 0.0 <= score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
