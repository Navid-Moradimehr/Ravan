"""Tests for the authentication/authorization module."""
from __future__ import annotations

import pytest


def test_password_hashing():
    from services.api_service.auth import hash_password, verify_password

    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_lifecycle():
    from services.api_service.auth import create_access_token, decode_access_token

    token = create_access_token("user-1", "operator")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "operator"
    assert payload["type"] == "access"


def test_auth_security_status_flags_default_secret():
    from services.api_service.auth import auth_security_status, is_default_jwt_secret

    status = auth_security_status()
    assert status["requires_operator_secret"] is True
    assert isinstance(status["jwt_secret_configured"], bool)
    assert is_default_jwt_secret() in (True, False)


def test_jwt_expired():
    from services.api_service.auth import create_access_token, decode_access_token
    import jwt
    import time
    import importlib

    import os
    orig = os.environ.get("JWT_EXPIRE_MINUTES")
    os.environ["JWT_EXPIRE_MINUTES"] = "0"
    # Reload the module so it picks up the new env value.
    from services.api_service import auth as auth_mod
    importlib.reload(auth_mod)
    token = auth_mod.create_access_token("user-1", "operator")
    time.sleep(1)
    with pytest.raises(jwt.ExpiredSignatureError):
        auth_mod.decode_access_token(token)
    if orig is not None:
        os.environ["JWT_EXPIRE_MINUTES"] = orig
    else:
        os.environ.pop("JWT_EXPIRE_MINUTES", None)
    importlib.reload(auth_mod)


def test_get_current_user_missing_header():
    from services.api_service.auth import get_current_user
    import pytest

    async def run():
        with pytest.raises(Exception):
            await get_current_user(None)

    import asyncio
    asyncio.run(run())


def test_get_current_user_invalid_token():
    from services.api_service.auth import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    import pytest

    async def run():
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
        with pytest.raises(Exception):
            await get_current_user(creds)

    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
