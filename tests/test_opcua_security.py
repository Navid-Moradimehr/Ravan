from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from services.edge_ingest.opcua_security import validate_security_material


def _certificate_and_key() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "datastream-test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=2))
        .sign(key, hashes.SHA256())
    )
    return (
        certificate.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()),
    )


def test_anonymous_opcua_security_does_not_require_material():
    assert validate_security_material({}, {"mode": "None"})["certificate_checked"] is False


def test_signed_opcua_security_requires_referenced_material():
    with pytest.raises(ValueError, match="requires certificate"):
        validate_security_material({}, {"mode": "SignAndEncrypt"})


def test_signed_opcua_security_checks_certificate_and_private_key():
    certificate, private_key = _certificate_and_key()
    result = validate_security_material(
        {"certificate": certificate.decode(), "private_key": private_key.decode()},
        {"mode": "SignAndEncrypt", "policy": "Basic256Sha256"},
    )
    assert result["certificate_checked"] is True
    assert result["days_remaining"] >= 1
