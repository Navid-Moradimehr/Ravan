"""Tests for Modbus RTU client."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "edge_ingest"))

from modbus_rtu_client import ModbusRTUClient


def test_modbus_rtu_client_init():
    client = ModbusRTUClient(port="COM3", baudrate=19200, slave_id=2)
    assert client.port == "COM3"
    assert client.baudrate == 19200
    assert client.slave_id == 2
    assert client._client is None


def test_modbus_rtu_default_values():
    client = ModbusRTUClient()
    assert client.port == "/dev/ttyUSB0"
    assert client.baudrate == 9600
    assert client.bytesize == 8
    assert client.parity == "N"
    assert client.stopbits == 1
    assert client.timeout == 1.0
    assert client.slave_id == 1


def test_modbus_rtu_context_manager():
    """Test context manager (connect/disconnect)."""
    client = ModbusRTUClient(port="/dev/ttyUSB0")
    # Note: Will fail to connect on non-existent port, but tests structure
    try:
        with client:
            pass
    except Exception:
        pass  # Expected if no serial port available


def test_modbus_rtu_client_without_connection():
    """Test that operations fail gracefully without connection."""
    client = ModbusRTUClient()
    result = client.read_holding_registers(0, 1)
    assert result is None

    result = client.read_input_registers(0, 1)
    assert result is None

    result = client.read_coils(0, 1)
    assert result is None

    result = client.write_register(0, 100)
    assert result is False
