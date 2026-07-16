"""Reference-only OPC UA certificate validation at the edge boundary."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import serialization


def _read_certificate(value: str) -> x509.Certificate:
    candidate = Path(value).expanduser() if "\n" not in value and len(value) < 4096 else None
    raw = candidate.read_bytes() if candidate is not None and candidate.exists() else value.encode("utf-8")
    try:
        return x509.load_pem_x509_certificate(raw)
    except ValueError:
        return x509.load_der_x509_certificate(raw)


def validate_security_material(credentials: dict[str, str], security: dict[str, Any]) -> dict[str, Any]:
    """Validate configured certificate references without exposing their contents."""
    mode = str(security.get("mode", "None"))
    if mode == "None":
        return {"mode": mode, "certificate_checked": False}
    certificate = str(credentials.get("certificate", "")).strip()
    private_key = str(credentials.get("private_key", "")).strip()
    if not certificate or not private_key:
        raise ValueError("OPC UA signed security requires certificate and private_key references")
    certificate_obj = _read_certificate(certificate)
    now = datetime.now(timezone.utc)
    not_before = getattr(certificate_obj, "not_valid_before_utc", None) or certificate_obj.not_valid_before.replace(tzinfo=timezone.utc)
    not_after = getattr(certificate_obj, "not_valid_after_utc", None) or certificate_obj.not_valid_after.replace(tzinfo=timezone.utc)
    if now < not_before:
        raise ValueError("OPC UA client certificate is not valid yet")
    if now > not_after:
        raise ValueError("OPC UA client certificate is expired")
    key_path = Path(private_key).expanduser() if "\n" not in private_key and len(private_key) < 4096 else None
    key_bytes = key_path.read_bytes() if key_path is not None and key_path.exists() else private_key.encode("utf-8")
    try:
        serialization.load_pem_private_key(key_bytes, password=None)
    except (ValueError, TypeError) as exc:
        raise ValueError("OPC UA private key reference does not contain a readable PEM key") from exc
    return {
        "mode": mode,
        "certificate_checked": True,
        "not_after": not_after.isoformat(),
        "days_remaining": max(0, int((not_after - now).total_seconds() // 86400)),
    }
