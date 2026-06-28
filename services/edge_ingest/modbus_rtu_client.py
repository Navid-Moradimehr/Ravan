"""Modbus RTU client for serial communication.

Extends existing pymodbus usage to support RTU/serial connections.
Open-source: pymodbus already supports RTU - just needs configuration.
"""
from __future__ import annotations

import logging
from typing import Any

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

logger = logging.getLogger(__name__)


class ModbusRTUClient:
    """Modbus RTU client wrapper for industrial serial devices."""

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 1.0,
        slave_id: int = 1,
    ):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.slave_id = slave_id
        self._client: ModbusSerialClient | None = None

    def connect(self) -> bool:
        """Connect to the Modbus RTU device."""
        self._client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
        )
        return self._client.connect()

    def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client:
            self._client.close()
            self._client = None

    def read_holding_registers(
        self, address: int, count: int = 1
    ) -> list[int] | None:
        """Read holding registers from the device."""
        if not self._client or not self._client.connected:
            logger.error("Modbus RTU client not connected")
            return None

        try:
            result = self._client.read_holding_registers(
                address=address, count=count, slave=self.slave_id
            )
            if result.isError():
                logger.error(f"Modbus error reading registers: {result}")
                return None
            return result.registers
        except ModbusException as e:
            logger.error(f"Modbus exception: {e}")
            return None

    def read_input_registers(
        self, address: int, count: int = 1
    ) -> list[int] | None:
        """Read input registers from the device."""
        if not self._client or not self._client.connected:
            logger.error("Modbus RTU client not connected")
            return None

        try:
            result = self._client.read_input_registers(
                address=address, count=count, slave=self.slave_id
            )
            if result.isError():
                logger.error(f"Modbus error reading input registers: {result}")
                return None
            return result.registers
        except ModbusException as e:
            logger.error(f"Modbus exception: {e}")
            return None

    def read_coils(self, address: int, count: int = 1) -> list[bool] | None:
        """Read coils from the device."""
        if not self._client or not self._client.connected:
            logger.error("Modbus RTU client not connected")
            return None

        try:
            result = self._client.read_coils(
                address=address, count=count, slave=self.slave_id
            )
            if result.isError():
                logger.error(f"Modbus error reading coils: {result}")
                return None
            return result.bits[:count]
        except ModbusException as e:
            logger.error(f"Modbus exception: {e}")
            return None

    def write_register(self, address: int, value: int) -> bool:
        """Write a single holding register."""
        if not self._client or not self._client.connected:
            logger.error("Modbus RTU client not connected")
            return False

        try:
            result = self._client.write_register(
                address=address, value=value, slave=self.slave_id
            )
            if result.isError():
                logger.error(f"Modbus error writing register: {result}")
                return False
            return True
        except ModbusException as e:
            logger.error(f"Modbus exception: {e}")
            return False

    def __enter__(self) -> "ModbusRTUClient":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()


def scan_modbus_rtu_devices(
    port: str = "/dev/ttyUSB0",
    baudrates: list[int] | None = None,
    slave_range: range = range(1, 10),
) -> list[dict[str, Any]]:
    """Scan for Modbus RTU devices on a serial port.

    Tries different baudrates and slave IDs to discover devices.
    """
    if baudrates is None:
        baudrates = [9600, 19200, 38400, 57600, 115200]

    found: list[dict[str, Any]] = []
    for baudrate in baudrates:
        for slave_id in slave_range:
            client = ModbusRTUClient(
                port=port, baudrate=baudrate, slave_id=slave_id, timeout=0.5
            )
            try:
                if client.connect():
                    result = client.read_holding_registers(0, 1)
                    if result is not None:
                        found.append({
                            "port": port,
                            "baudrate": baudrate,
                            "slave_id": slave_id,
                            "registers": result,
                        })
                        logger.info(
                            f"Found device at {port}:{baudrate}, slave {slave_id}"
                        )
            except Exception as e:
                logger.debug(f"No response at {baudrate}/{slave_id}: {e}")
            finally:
                client.disconnect()

    return found
