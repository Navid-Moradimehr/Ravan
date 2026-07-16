"""Shared Modbus register-map decoding for TCP and RTU connectors."""
from __future__ import annotations

import struct
from typing import Any

MODBUS_DATA_TYPES = {
    "uint16", "int16", "bool", "uint32", "int32", "float32",
    "uint64", "int64", "float64",
}
MODBUS_BYTE_ORDERS = {"big", "little"}
MODBUS_WORD_ORDERS = {"big", "little"}


def register_count(data_type: str) -> int:
    return 4 if data_type in {"uint64", "int64", "float64"} else 2 if data_type in {"uint32", "int32", "float32"} else 1


def decode_registers(registers: list[int], data_type: str, byte_order: str = "big", word_order: str = "big") -> float | bool:
    values = [int(value) & 0xFFFF for value in registers]
    if byte_order == "little":
        values = [((value & 0xFF) << 8) | (value >> 8) for value in values]
    raw = b"".join(value.to_bytes(2, "big") for value in values)
    if word_order == "little":
        chunks = [raw[index:index + 2] for index in range(0, len(raw), 2)]
        raw = b"".join(chunks[::-1])
    if data_type == "bool":
        return bool(values[0])
    formats = {
        "uint16": ">H", "int16": ">h", "uint32": ">I", "int32": ">i",
        "float32": ">f", "uint64": ">Q", "int64": ">q", "float64": ">d",
    }
    return struct.unpack(formats[data_type], raw[:struct.calcsize(formats[data_type])])[0]


def normalize_register(item: dict[str, Any]) -> dict[str, Any]:
    data_type = str(item.get("data_type", "uint16")).lower()
    return {
        "address": int(item["address"]),
        "tag": str(item.get("tag", f"register_{item['address']}")),
        "unit": str(item.get("unit", "")),
        "scale": float(item.get("scale", 1.0)),
        "offset": float(item.get("offset", 0.0)),
        "unit_id": int(item.get("unit_id", item.get("slave_id", 1))),
        "data_type": data_type,
        "byte_order": str(item.get("byte_order", "big")).lower(),
        "word_order": str(item.get("word_order", "big")).lower(),
        "count": register_count(data_type),
    }
