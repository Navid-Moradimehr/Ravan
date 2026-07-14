"""Resolve operator-owned connection references at the edge boundary.

The registry stores references only. This module is the deliberately small
bridge to deployment-owned secret providers; it never returns resolved values
through an API response or persists them.
"""
from __future__ import annotations

import os
from pathlib import Path


class CredentialResolutionError(RuntimeError):
    pass


def resolve_reference(reference: str) -> str:
    value = str(reference or "").strip()
    if value.startswith("env://"):
        name = value.removeprefix("env://").strip()
        resolved = os.getenv(name, "")
        if not resolved:
            raise CredentialResolutionError(f"environment credential {name!r} is not set")
        return resolved
    if value.startswith("file://"):
        path = value.removeprefix("file://")
        resolved = Path(path).expanduser().read_text(encoding="utf-8").strip()
        if not resolved:
            raise CredentialResolutionError(f"credential file {path!r} is empty")
        return resolved
    if value.startswith("path://"):
        path = value.removeprefix("path://")
        if not Path(path).expanduser().exists():
            raise CredentialResolutionError(f"credential path {path!r} does not exist")
        return str(Path(path).expanduser())
    if value.startswith("secret://"):
        raise CredentialResolutionError(
            "secret:// references require a deployment secret provider; configure an env://, file://, or path:// reference for this runtime"
        )
    raise CredentialResolutionError("credential reference must use env://, file://, or secret://")


def resolve_credentials(references: dict[str, str] | None) -> dict[str, str]:
    return {key: resolve_reference(value) for key, value in (references or {}).items()}
