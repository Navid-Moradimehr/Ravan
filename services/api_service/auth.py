"""Authentication & authorization for the API service.

- Password hashing with bcrypt (passlib)
- JWT token issuance/validation (PyJWT)
- FastAPI dependencies: get_current_user, require_permission
- Persistent user/audit storage in the historian DB
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

# Optional PyJWT import with fallback error message
try:
    import jwt
except ImportError:  # pragma: no cover
    raise RuntimeError("PyJWT is required for authentication. Install with: pip install PyJWT")

try:
    from rbac import Role, Permission, User, AuditLog, audit_log as _mem_audit_log
except ImportError:
    from services.api_service.rbac import Role, Permission, User, AuditLog, audit_log as _mem_audit_log  # type: ignore

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_JWT_SECRET = "change-me-in-production-please-set-a-long-secret"
JWT_SECRET = os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    import bcrypt
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, role: str, tenant_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "tenant": tenant_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def is_default_jwt_secret() -> bool:
    return JWT_SECRET == DEFAULT_JWT_SECRET


def is_jwt_secret_strong_enough() -> bool:
    return len(JWT_SECRET) >= 32


def auth_security_status() -> dict[str, Any]:
    return {
        "jwt_secret_configured": not is_default_jwt_secret(),
        "jwt_secret_strong_enough": is_jwt_secret_strong_enough(),
        "jwt_algorithm": JWT_ALGORITHM,
        "jwt_expire_minutes": JWT_EXPIRE_MINUTES,
        "requires_operator_secret": True,
    }


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Try DB-backed users first, then fallback to in-memory (dev/demo)
    user = _get_db_user(user_id) or _get_mem_user(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_permission(permission: Permission):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"User {user.username} lacks permission {permission.value}",
            )
        return user
    return _checker


# ---------------------------------------------------------------------------
# Persistent user storage (best-effort DB, fallback to in-memory)
# ---------------------------------------------------------------------------
_db_users: dict[str, User] = {}
_db_loaded = False


def _get_db_user(user_id: str) -> User | None:
    global _db_loaded
    if not _db_loaded:
        _load_users_from_db()
    return _db_users.get(user_id)


def _get_mem_user(user_id: str) -> User | None:
    from rbac import users_db
    return users_db.get(user_id)


def _load_users_from_db() -> None:
    global _db_loaded
    try:
        from services.historian.client import query_sql
    except ImportError:
        from historian.client import query_sql  # type: ignore
    try:
        rows = query_sql(
            "SELECT user_id, username, role, email, password_hash FROM users ORDER BY created_at DESC",
        )
        for row in rows:
            _db_users[row["user_id"]] = User(
                user_id=row["user_id"],
                username=row["username"],
                role=Role(row["role"]),
                email=row.get("email"),
            )
            # Store hash separately so authenticate_user can look it up.
            _password_hashes[row["user_id"]] = row.get("password_hash", "")
    except Exception:
        pass
    _db_loaded = True


_password_hashes: dict[str, str] = {}


def authenticate_user(username: str, password: str) -> User | None:
    """Authenticate against DB-backed users (with in-memory fallback)."""
    # Ensure DB cache is warm.
    _load_users_from_db()

    # Search DB cache first.
    for user_id, user in _db_users.items():
        if user.username == username:
            if verify_password(password, _password_hashes.get(user_id, "")):
                return user

    # Fallback to in-memory (dev/demo where passwords aren't hashed).
    from rbac import users_db as mem_users
    for user in mem_users.values():
        if user.username == username:
            return user
    return None


def create_user(
    user_id: str,
    username: str,
    role: Role,
    email: str | None = None,
    password: str | None = None,
) -> User:
    """Create a user in DB (with in-memory fallback)."""
    hashed = hash_password(password) if password else ""
    user = User(user_id, username, role, email)

    try:
        from services.historian.client import query_sql
    except ImportError:
        from historian.client import query_sql  # type: ignore
    try:
        query_sql(
            """
            INSERT INTO users (user_id, username, role, email, password_hash, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                role = EXCLUDED.role,
                email = EXCLUDED.email,
                password_hash = EXCLUDED.password_hash
            """,
            (user_id, username, role.value, email, hashed, datetime.now(timezone.utc).isoformat()),
        )
    except Exception:
        pass

    # Also keep in-memory for immediate use without DB round-trip.
    _db_users[user_id] = user
    _password_hashes[user_id] = hashed
    _mem_audit_log.log(user_id, "user_created", "users", {"role": role.value})
    return user


# ---------------------------------------------------------------------------
# Audit log persistence (best-effort DB)
# ---------------------------------------------------------------------------
class _PersistentAuditLog(AuditLog):
    """Wraps the in-memory audit log with best-effort DB persistence."""

    def log(self, user_id: str, action: str, resource: str, details: dict[str, Any] | None = None) -> None:
        super().log(user_id, action, resource, details)
        try:
            from services.historian.client import query_sql
        except ImportError:
            from historian.client import query_sql  # type: ignore
        try:
            query_sql(
                """
                INSERT INTO audit_logs (time, user_id, action, resource, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    user_id,
                    action,
                    resource,
                    details or {},
                ),
            )
        except Exception:
            pass


# Replace the global in-memory audit log with the persistent wrapper.
audit_log = _PersistentAuditLog()
