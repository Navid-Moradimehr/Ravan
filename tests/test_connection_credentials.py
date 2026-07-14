from __future__ import annotations

from pathlib import Path

import pytest

from services.edge_ingest.credentials import CredentialResolutionError, resolve_credentials, resolve_reference


def test_resolve_env_reference(monkeypatch):
    monkeypatch.setenv("DATASTREAM_TEST_SECRET", "secret-value")
    assert resolve_reference("env://DATASTREAM_TEST_SECRET") == "secret-value"


def test_resolve_file_and_path_references(tmp_path: Path):
    secret_file = tmp_path / "password"
    certificate = tmp_path / "client.crt"
    secret_file.write_text("password-value\n", encoding="utf-8")
    certificate.write_text("certificate", encoding="utf-8")
    assert resolve_reference(f"file://{secret_file}") == "password-value"
    assert resolve_reference(f"path://{certificate}") == str(certificate)


def test_secret_provider_reference_is_explicitly_unavailable():
    with pytest.raises(CredentialResolutionError, match="secret://"):
        resolve_reference("secret://plant/password")


def test_resolve_credentials_does_not_accept_raw_values():
    with pytest.raises(CredentialResolutionError):
        resolve_credentials({"password": "plain-text"})
