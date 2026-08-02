from datetime import datetime, timezone

import pytest

from services.common.device_compat import device_profile
from services.common.versal_contract import VersalMetric, device_profile_config
from services.edge_ingest.versal_simulator import build_manifest, iter_metrics


def test_versal_profile_reuses_supported_gateway_protocols():
    profile = device_profile("amd_versal_v1")
    assert profile and profile["protocols"] == ("sparkplug_b", "opcua")
    assert device_profile_config(board="vck190", device_id="dev-1")["gateway_protocol"] == "sparkplug_b"


def test_versal_metric_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError):
        VersalMetric(asset_id="a", tag="latency", value=1, ts_source="2026-01-01T00:00:00")


def test_simulator_manifest_separates_scalar_metrics_and_waveform_reference():
    manifest = build_manifest(source_id="versal-1", site_id="plant-a")
    assert manifest.simulator == "gateway"
    assert len(manifest.metrics) == 20
    assert manifest.artifacts[0].modality == "waveform"
    assert manifest.artifacts[0].uri.startswith("file://")
    assert all(metric.metadata["device_profile"] == "amd_versal_v1" for metric in manifest.metrics)


def test_simulator_sequence_is_deterministic():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = list(iter_metrics(source_id="v", site_id="s", start=start, count=2))
    second = list(iter_metrics(source_id="v", site_id="s", start=start, count=2))
    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]


def test_soak_profile_keeps_mcp_and_versal_acceptance_budgets_explicit():
    import yaml

    with open("config/benchmarks/versal-mcp-soak.yaml", encoding="utf-8") as handle:
        profile = yaml.safe_load(handle)
    assert profile["duration_seconds"] == 900
    assert profile["acceptance"]["max_mcp_errors"] == 0
    assert profile["versal"]["gateway_protocols"] == ["sparkplug_b", "opcua"]
