"""Audit logging service for tracking all operations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import structlog

from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class AuditAction(str, Enum):
    """Actions that can be audited."""
    # Fragment operations
    FRAGMENT_CREATE = "fragment:create"
    FRAGMENT_READ = "fragment:read"
    FRAGMENT_UPDATE = "fragment:update"
    FRAGMENT_DELETE = "fragment:delete"
    FRAGMENT_SEARCH = "fragment:search"
    
    # Execution operations
    EXECUTE_REQUEST = "execute:request"
    EXECUTE_REUSE = "execute:reuse"
    EXECUTE_ADAPT = "execute:adapt"
    EXECUTE_RECOMPUTE = "execute:recompute"
    
    # Feedback
    FEEDBACK_CREATE = "feedback:create"
    FEEDBACK_READ = "feedback:read"
    
    # Versioning
    VERSION_CREATE = "version:create"
    VERSION_ROLLBACK = "version:rollback"
    VERSION_READ = "version:read"
    
    # Clustering
    CLUSTERING_RUN = "clustering:run"
    CLUSTERING_READ = "clustering:read"
    
    # Admin
    ADMIN_PRUNE = "admin:prune"
    ADMIN_DECAY = "admin:decay"
    ADMIN_METRICS = "admin:metrics"
    
    # Auth
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    AUTH_DENIED = "auth:denied"


class AuditLevel(str, Enum):
    """Audit event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event record."""
    event_id: str
    timestamp: datetime
    action: AuditAction
    level: AuditLevel
    user_id: str
    resource_type: str
    resource_id: str | None
    details: dict[str, Any]
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool = True
    error_message: str | None = None


@dataclass
class AuditLog:
    """Audit log storage."""
    events: list[AuditEvent] = field(default_factory=list)
    _file_path: str | None = None
    
    def add_event(self, event: AuditEvent) -> None:
        """Add event to log."""
        self.events.append(event)
        
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.action.value,
                    "level": e.level.value,
                    "user_id": e.user_id,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "details": e.details,
                    "ip_address": e.ip_address,
                    "user_agent": e.user_agent,
                    "success": e.success,
                    "error_message": e.error_message,
                }
                for e in self.events
            ]
        }


class AuditService:
    """Service for audit logging."""

    def __init__(self):
        settings = get_settings()
        self.enabled = getattr(settings, 'audit_enabled', True)
        self.file_path = getattr(settings, 'audit_log_path', './data/audit.json')
        self.max_events = getattr(settings, 'audit_max_events', 10000)
        
        if self.enabled:
            self._log = AuditLog(_file_path=self.file_path)
            self._load_existing()
        else:
            self._log = AuditLog()

    def _load_existing(self) -> None:
        """Load existing audit log from file."""
        if not os.path.exists(self.file_path):
            return
        
        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
                events = data.get("events", [])
                for e in events:
                    self._log.events.append(AuditEvent(
                        event_id=e["event_id"],
                        timestamp=datetime.fromisoformat(e["timestamp"]).replace(tzinfo=timezone.utc),
                        action=AuditAction(e["action"]),
                        level=AuditLevel(e["level"]),
                        user_id=e["user_id"],
                        resource_type=e["resource_type"],
                        resource_id=e.get("resource_id"),
                        details=e.get("details", {}),
                        ip_address=e.get("ip_address"),
                        user_agent=e.get("user_agent"),
                        success=e.get("success", True),
                        error_message=e.get("error_message"),
                    ))
        except Exception as e:
            logger.warning("audit_load_failed", error=str(e))

    def _save(self) -> None:
        """Save audit log to file."""
        if not self.enabled:
            return
            
        parent = os.path.dirname(self.file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._log.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error("audit_save_failed", error=str(e))

    def log(
        self,
        action: AuditAction,
        user_id: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        level: AuditLevel = AuditLevel.INFO,
        success: bool = True,
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Log an audit event."""
        import uuid
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=action,
            level=level,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        
        self._log.add_event(event)
        
        if len(self._log.events) > self.max_events:
            self._log.events = self._log.events[-self.max_events:]
        
        self._save()
        
        log_level = level.value
        logger.log(log_level, "audit_event", 
                   action=action.value, 
                   user_id=user_id,
                   resource_id=resource_id,
                   success=success)
        
        return event

    def log_fragment_operation(
        self,
        operation: AuditAction,
        user_id: str,
        fragment_id: str,
        success: bool = True,
        details: dict | None = None,
    ) -> AuditEvent:
        """Log fragment operation."""
        return self.log(
            action=operation,
            user_id=user_id,
            resource_type="fragment",
            resource_id=fragment_id,
            details=details,
            success=success,
        )

    def log_execution(
        self,
        decision: str,
        user_id: str,
        execution_id: str,
        fragment_id: str | None = None,
        cost: float | None = None,
    ) -> AuditEvent:
        """Log execution."""
        action_map = {
            "reuse": AuditAction.EXECUTE_REUSE,
            "adapt": AuditAction.EXECUTE_ADAPT,
            "recompute": AuditAction.EXECUTE_RECOMPUTE,
        }
        
        return self.log(
            action=action_map.get(decision, AuditAction.EXECUTE_REQUEST),
            user_id=user_id,
            resource_type="execution",
            resource_id=execution_id,
            details={"fragment_id": fragment_id, "cost": cost},
            success=True,
        )

    def log_auth(
        self,
        operation: AuditAction,
        user_id: str,
        success: bool = True,
        error_message: str | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log authentication event."""
        return self.log(
            action=operation,
            user_id=user_id,
            resource_type="auth",
            resource_id=user_id,
            success=success,
            error_message=error_message,
            level=AuditLevel.WARNING if not success else AuditLevel.INFO,
            ip_address=ip_address,
        )

    def get_events(
        self,
        user_id: str | None = None,
        action: AuditAction | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events."""
        events = self._log.events
        
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if action:
            events = [e for e in events if e.action == action]
        if resource_type:
            events = [e for e in events if e.resource_type == resource_type]
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    def get_user_activity(self, user_id: str, limit: int = 50) -> list[AuditEvent]:
        """Get user activity."""
        return self.get_events(user_id=user_id, limit=limit)

    def get_resource_history(self, resource_type: str, resource_id: str, limit: int = 50) -> list[AuditEvent]:
        """Get resource history."""
        events = [
            e for e in self._log.events
            if e.resource_type == resource_type and e.resource_id == resource_id
        ]
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        total = len(self._log.events)
        by_action: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_user: dict[str, int] = {}
        
        for event in self._log.events:
            action_key = event.action.value
            by_action[action_key] = by_action.get(action_key, 0) + 1
            
            level_key = event.level.value
            by_level[level_key] = by_level.get(level_key, 0) + 1
            
            by_user[event.user_id] = by_user.get(event.user_id, 0) + 1
        
        return {
            "total_events": total,
            "by_action": by_action,
            "by_level": by_level,
            "by_user": by_user,
        }


def get_audit_service() -> AuditService:
    """Get singleton audit service."""
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = AuditService()
    return _audit_service_instance


_audit_service_instance = None