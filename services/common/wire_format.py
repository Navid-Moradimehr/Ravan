from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from typing import Any

from services.common.native_fastpath import json_bytes as native_json_bytes

try:
    import msgpack
except ImportError:  # pragma: no cover - optional binary fast path
    msgpack = None

try:
    import orjson
except ImportError:  # pragma: no cover - optional fast path
    orjson = None

WIRE_FORMAT_JSON = "json"
WIRE_FORMAT_MSGPACK = "msgpack"


def _normalize_payload(payload: Any) -> Any:
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
    if is_dataclass(payload):
        payload = asdict(payload)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="python", exclude_none=False, by_alias=False)
    return payload


def _resolved_wire_format(wire_format: str | None = None) -> str:
    if wire_format:
        return wire_format.lower()
    return os.getenv("DATASTREAM_WIRE_FORMAT", WIRE_FORMAT_JSON).lower()


def serialize_payload(payload: Any, wire_format: str | None = None) -> bytes:
    normalized = _normalize_payload(payload)
    format_name = _resolved_wire_format(wire_format)
    if format_name == WIRE_FORMAT_MSGPACK:
        if msgpack is None:
            raise RuntimeError("msgpack is required for DATASTREAM_WIRE_FORMAT=msgpack")
        return msgpack.packb(normalized, use_bin_type=True)
    native = native_json_bytes(normalized)
    if native is not None:
        return native
    if orjson is not None:
        return orjson.dumps(normalized)
    return json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def deserialize_payload(data: bytes, wire_format: str | None = None) -> Any:
    format_name = _resolved_wire_format(wire_format)
    if format_name == WIRE_FORMAT_MSGPACK:
        if msgpack is None:
            raise RuntimeError("msgpack is required for DATASTREAM_WIRE_FORMAT=msgpack")
        return msgpack.unpackb(data, raw=False)
    return json.loads(data.decode("utf-8"))
