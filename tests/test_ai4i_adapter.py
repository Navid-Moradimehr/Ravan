from __future__ import annotations

from services.datasets.ai4i_adapter import map_ai4i_row


def test_map_ai4i_normal_row() -> None:
    row = {
        "UDI": "1",
        "Product ID": "L47181",
        "Type": "M",
        "Air temperature [K]": "300.1",
        "Process temperature [K]": "310.2",
        "Rotational speed [rpm]": "1500",
        "Torque [Nm]": "40.5",
        "Tool wear [min]": "10",
        "Machine failure": "0",
        "TWF": "0",
        "HDF": "0",
        "PWF": "0",
        "OSF": "0",
        "RNF": "0",
    }
    events = map_ai4i_row(row, "M-1")
    tags = {e["tag"] for e in events}
    assert "AirTemperature" in tags
    assert "ProcessTemperature" in tags
    assert "RotationalSpeed" in tags
    assert "Torque" in tags
    assert "ToolWear" in tags
    assert all(e["quality"] == "good" for e in events)


def test_map_ai4i_failure_row() -> None:
    row = {
        "UDI": "2",
        "Product ID": "L47182",
        "Type": "L",
        "Air temperature [K]": "305.0",
        "Process temperature [K]": "315.0",
        "Rotational speed [rpm]": "1200",
        "Torque [Nm]": "55.0",
        "Tool wear [min]": "200",
        "Machine failure": "1",
        "TWF": "1",
        "HDF": "0",
        "PWF": "0",
        "OSF": "0",
        "RNF": "0",
    }
    events = map_ai4i_row(row, "M-2")
    sensor_events = [e for e in events if e["tag"] != "MachineFailure"]
    assert all(e["quality"] == "bad" for e in sensor_events)
    failure_events = [e for e in events if e["tag"] == "MachineFailure"]
    assert len(failure_events) == 1
    assert failure_events[0]["value"] == 1.0
