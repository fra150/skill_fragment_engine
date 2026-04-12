"""RBAC (Role-Based Access Control) for SFE APIs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable

import structlog

from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class Role(str, Enum):
    """User roles."""
    ADMIN = "admin"
    POWER_USER = "power_user"
    USER = "user"
    READONLY = "readonly"
    GUEST = "guest"


class Permission(str, Enum):
    """Permissions."""
    # Fragments
    FRAGMENT_READ = "fragment:read"
    FRAGMENT_WRITE = "fragment:write"
    FRAGMENT_DELETE = "fragment:delete"
    FRAGMENT_SEARCH = "fragment:search"
    
    # Execution
    EXECUTE_READ = "execute:read"
    EXECUTE_WRITE = "execute:write"
    
    # Feedback
    FEEDBACK_READ = "feedback:read"
    FEEDBACK_WRITE = "feedback:write"
    
    # Versioning
    VERSION_READ = "version:read"
    VERSION_WRITE = "version:write"
    VERSION_ROLLBACK = "version:rollback"
    
    # Clustering
    CLUSTERING_READ = "clustering:read"
    CLUSTERING_WRITE = "clustering:write"
    
    # Admin
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_METRICS = "admin:metrics"
    ADMIN_PRUNE = "admin:prune"
    ADMIN_DECAY = "admin:decay"
    
    # Settings
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"


ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.ADMIN: [
        Permission.FRAGMENT_READ, Permission.FRAGMENT_WRITE, Permission.FRAGMENT_DELETE,
        Permission.FRAGMENT_SEARCH, Permission.EXECUTE_READ, Permission.EXECUTE_WRITE,
        Permission.FEEDBACK_READ, Permission.FEEDBACK_WRITE,
        Permission.VERSION_READ, Permission.VERSION_WRITE, Permission.VERSION_ROLLBACK,
        Permission.CLUSTERING_READ, Permission.CLUSTERING_WRITE,
        Permission.ADMIN_READ, Permission.ADMIN_WRITE, Permission.ADMIN_METRICS,
        Permission.ADMIN_PRUNE, Permission.ADMIN_DECAY,
        Permission.SETTINGS_READ, Permission.SETTINGS_WRITE,
    ],
    Role.POWER_USER: [
        Permission.FRAGMENT_READ, Permission.FRAGMENT_WRITE, Permission.FRAGMENT_SEARCH,
        Permission.EXECUTE_READ, Permission.EXECUTE_WRITE,
        Permission.FEEDBACK_READ, Permission.FEEDBACK_WRITE,
        Permission.VERSION_READ, Permission.VERSION_WRITE,
        Permission.CLUSTERING_READ, Permission.CLUSTERING_WRITE,
        Permission.ADMIN_READ, Permission.ADMIN_METRICS,
        Permission.SETTINGS_READ,
    ],
    Role.USER: [
        Permission.FRAGMENT_READ, Permission.FRAGMENT_SEARCH,
        Permission.EXECUTE_READ, Permission.EXECUTE_WRITE,
        Permission.FEEDBACK_READ, Permission.FEEDBACK_WRITE,
        Permission.VERSION_READ,
        Permission.CLUSTERING_READ,
        Permission.ADMIN_READ,
    ],
    Role.READONLY: [
        Permission.FRAGMENT_READ, Permission.FRAGMENT_SEARCH,
        Permission.EXECUTE_READ,
        Permission.FEEDBACK_READ,
        Permission.VERSION_READ,
        Permission.CLUSTERING_READ,
        Permission.ADMIN_READ, Permission.ADMIN_METRICS,
    ],
    Role.GUEST: [
        Permission.FRAGMENT_READ,
        Permission.EXECUTE_READ,
    ],
}


@dataclass
class User:
    """User model with role."""
    user_id: str
    role: Role
    metadata: dict[str, Any] | None = None


class RBACService:
    """RBAC service for managing access control."""

    def __init__(self):
        settings = get_settings()
        self.enabled = getattr(settings, 'rbac_enabled', False)
        
        if self.enabled:
            default_role = getattr(settings, 'rbac_default_role', 'user')
            self.default_role = Role(default_role)
        else:
            self.default_role = Role.ADMIN
            
        self._users: dict[str, User] = {}

    def register_user(self, user_id: str, role: Role, metadata: dict | None = None) -> User:
        """Register a user with a role."""
        user = User(user_id=user_id, role=role, metadata=metadata)
        self._users[user_id] = user
        logger.info("user_registered", user_id=user_id, role=role.value)
        return user

    def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        return self._users.get(user_id)

    def update_role(self, user_id: str, new_role: Role) -> bool:
        """Update user's role."""
        if user_id not in self._users:
            return False
        self._users[user_id].role = new_role
        logger.info("role_updated", user_id=user_id, new_role=new_role.value)
        return True

    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if user has permission."""
        if not self.enabled:
            return True
            
        user = self._users.get(user_id)
        if user is None:
            user = User(user_id=user_id, role=self.default_role)
            
        allowed_permissions = ROLE_PERMISSIONS.get(user.role, [])
        return permission in allowed_permissions

    def has_any_permission(self, user_id: str, permissions: list[Permission]) -> bool:
        """Check if user has any of the permissions."""
        return any(self.has_permission(user_id, p) for p in permissions)

    def has_all_permissions(self, user_id: str, permissions: list[Permission]) -> bool:
        """Check if user has all permissions."""
        return all(self.has_permission(user_id, p) for p in permissions)

    def get_user_permissions(self, user_id: str) -> list[Permission]:
        """Get all permissions for a user."""
        user = self._users.get(user_id)
        if user is None:
            user = User(user_id=user_id, role=self.default_role)
        return ROLE_PERMISSIONS.get(user.role, [])

    def get_role_permissions(self, role: Role) -> list[Permission]:
        """Get permissions for a role."""
        return ROLE_PERMISSIONS.get(role, [])


def require_permission(permission: Permission):
    """Decorator to require a permission for an endpoint."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import HTTPException, Request, status
            
            request = kwargs.get('request') or (args[0] if args and isinstance(args[0], Request) else None)
            
            if request is None:
                return await func(*args, **kwargs)
            
            rbac = get_rbac_service()
            user_id = getattr(request.state, 'user_id', 'anonymous')
            
            if not rbac.has_permission(user_id, permission):
                logger.warning("permission_denied", user_id=user_id, permission=permission.value)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: Role):
    """Decorator to require a specific role."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import HTTPException, Request, status
            
            request = kwargs.get('request') or (args[0] if args and isinstance(args[0], Request) else None)
            
            if request is None:
                return await func(*args, **kwargs)
            
            rbac = get_rbac_service()
            user_id = getattr(request.state, 'user_id', 'anonymous')
            user = rbac.get_user(user_id)
            
            required_roles = [role]
            if role == Role.ADMIN:
                required_roles = [Role.ADMIN]
            elif role == Role.POWER_USER:
                required_roles = [Role.ADMIN, Role.POWER_USER]
            
            if user is None or user.role not in required_roles:
                logger.warning("role_denied", user_id=user_id, required_role=role.value)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_rbac_service() -> RBACService:
    """Get singleton RBAC service."""
    global _rbac_service_instance
    if _rbac_service_instance is None:
        _rbac_service_instance = RBACService()
    return _rbac_service_instance


_rbac_service_instance = None