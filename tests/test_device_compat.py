from __future__ import annotations

from services.common.device_compat import protocol_profile, supported_protocols, tag_to_legacy_field, unit_for_tag


def test_supported_protocols_include_industrial_edge_families() -> None:
    protocols = supported_protocols()
    assert "opcua" in protocols
    assert "modbus" in protocols
    assert "modbus_rtu" in protocols
    assert "mqtt" in protocols
    assert "sparkplug_b" in protocols


def test_protocol_profile_describes_common_edge_families() -> None:
    opcua = protocol_profile("opcua")
    modbus = protocol_profile("modbus")

    assert opcua is not None
    assert "heterogeneous" in " ".join(opcua.notes)
    assert modbus is not None
    assert "brownfield" in " ".join(modbus.notes)


def test_shared_tag_mapping_is_consistent() -> None:
    assert tag_to_legacy_field("Pump Temperature") == "temperature_c"
    assert tag_to_legacy_field("Motor Vibration") == "vibration_mm_s"
    assert unit_for_tag("Header Pressure") == "bar"
