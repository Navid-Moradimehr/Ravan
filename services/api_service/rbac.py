from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
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
tenants_db: dict[str, "Tenant"] = {}

@dataclass
class Tenant:
    tenant_id: str
    name: str
    namespace: str  # Kafka topic prefix / DB schema prefix
    owner_user_id: str
    allowed_domains: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            import datetime
            self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "namespace": self.namespace,
            "owner_user_id": self.owner_user_id,
            "allowed_domains": self.allowed_domains,
            "created_at": self.created_at,
        }

def create_tenant(tenant_id: str, name: str, namespace: str, owner_user_id: str, allowed_domains: list[str] | None = None) -> Tenant:
    tenant = Tenant(tenant_id, name, namespace, owner_user_id, allowed_domains or [])
    tenants_db[tenant_id] = tenant
    audit_log.log(owner_user_id, "tenant_created", "tenants", {"tenant_id": tenant_id, "namespace": namespace})
    return tenant

def get_tenant(tenant_id: str) -> Tenant | None:
    return tenants_db.get(tenant_id)

def list_tenants() -> list[Tenant]:
    return list(tenants_db.values())


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
