from __future__ import annotations

from enum import Enum
from typing import Any

class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.ADMIN: [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN],
    Role.OPERATOR: [Permission.READ, Permission.WRITE],
    Role.VIEWER: [Permission.READ],
}

class User:
    def __init__(self, user_id: str, username: str, role: Role, email: str | None = None):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.email = email

    def has_permission(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "email": self.email,
        }

class AuditLog:
    def __init__(self):
        self._logs: list[dict[str, Any]] = []

    def log(self, user_id: str, action: str, resource: str, details: dict[str, Any] | None = None) -> None:
        import datetime
        self._logs.append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "details": details or {},
        })

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._logs[-limit:]

audit_log = AuditLog()

users_db: dict[str, User] = {}

def create_user(user_id: str, username: str, role: Role, email: str | None = None) -> User:
    user = User(user_id, username, role, email)
    users_db[user_id] = user
    audit_log.log(user_id, "user_created", "users", {"role": role.value})
    return user

def get_user(user_id: str) -> User | None:
    return users_db.get(user_id)

def authenticate_user(username: str, password: str) -> User | None:
    # Simple mock auth for demo
    for user in users_db.values():
        if user.username == username:
            return user
    return None

def require_permission(user: User, permission: Permission) -> None:
    if not user.has_permission(permission):
        raise PermissionError(f"User {user.username} lacks permission {permission.value}")
