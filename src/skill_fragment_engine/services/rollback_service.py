"""Rollback service for automatic failure recovery."""

from __future__ import annotations

import structlog
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class RollbackStrategy(str, Enum):
    """Available rollback strategies."""
    
    RESTORE_PREVIOUS_VERSION = "restore_previous_version"
    RESTORE_LAST_VALID = "restore_last_valid"
    FALLBACK_TO_SAFE = "fallback_to_safe"
    CREATE_NEW_VERSION = "create_new_version"


class RollbackRecord:
    """Record of a rollback operation."""
    
    def __init__(
        self,
        rollback_id: UUID,
        fragment_id: UUID,
        previous_version: int,
        target_version: int,
        trigger: str,
        executed_at: datetime,
        success: bool,
        error_message: str | None = None,
    ):
        self.rollback_id = rollback_id
        self.fragment_id = fragment_id
        self.previous_version = previous_version
        self.target_version = target_version
        self.trigger = trigger
        self.executed_at = executed_at
        self.success = success
        self.error_message = error_message


class RollbackService:
    """
    Service for automatic rollback on failed executions.
    
    Features:
    - Detect when rollback is needed
    - Automatically restore previous valid state
    - Track rollback history
    - Configure rollback policies
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Rollback configuration
        self._max_retries_before_rollback = 3
        self._failure_threshold = 0.5  # 50% failure rate triggers rollback
        self._rollback_history: list[RollbackRecord] = []
        
        # Safe versions storage (versions known to work)
        self._safe_versions: dict[str, int] = {}  # fragment_id -> safe version number
    
    async def should_rollback(
        self,
        fragment_id: str,
        recent_failures: int,
        recent_executions: int,
    ) -> tuple[bool, str]:
        """
        Determine if rollback should be triggered.
        
        Args:
            fragment_id: ID of the fragment
            recent_failures: Number of recent failures
            recent_executions: Number of recent executions
            
        Returns:
            Tuple of (should_rollback, reason)
        """
        if recent_executions == 0:
            return False, "No recent executions"
        
        failure_rate = recent_failures / recent_executions
        
        # Check failure threshold
        if failure_rate >= self._failure_threshold:
            return True, f"Failure rate {failure_rate:.1%} exceeds threshold {self._failure_threshold:.1%}"
        
        # Check retry count
        if recent_failures >= self._max_retries_before_rollback:
            return True, f"Failure count {recent_failures} exceeds max retries {self._max_retries_before_rollback}"
        
        return False, "Failure rate within acceptable range"
    
    async def execute_rollback(
        self,
        fragment_id: str,
        strategy: RollbackStrategy = RollbackStrategy.RESTORE_LAST_VALID,
        versioning_service=None,
    ) -> RollbackRecord:
        """
        Execute a rollback operation.
        
        Args:
            fragment_id: ID of the fragment to rollback
            strategy: Rollback strategy to use
            versioning_service: Optional versioning service for version management
            
        Returns:
            RollbackRecord with operation details
        """
        rollback_id = uuid4()
        executed_at = datetime.utcnow()
        
        try:
            if versioning_service is None:
                # Import versioning service if not provided
                from skill_fragment_engine.services.versioning_service import get_versioning_service
                versioning_service = get_versioning_service()
            
            # Get current version
            current_version = versioning_service.get_active_version(fragment_id)
            previous_version_num = current_version.version_number if current_version else 1
            
            # Determine target version based on strategy
            target_version_num = await self._determine_target_version(
                fragment_id, strategy, versioning_service
            )
            
            # Execute the rollback via versioning service
            if target_version_num:
                result = versioning_service.rollback_to_version(
                    fragment_id=fragment_id,
                    version_number=target_version_num,
                    reason=f"Automatic rollback triggered by failure (strategy: {strategy.value})",
                )
                
                # Mark as safe version
                self._safe_versions[fragment_id] = target_version_num
                
                record = RollbackRecord(
                    rollback_id=rollback_id,
                    fragment_id=UUID(fragment_id) if self._is_valid_uuid(fragment_id) else uuid4(),
                    previous_version=previous_version_num,
                    target_version=target_version_num,
                    trigger=strategy.value,
                    executed_at=executed_at,
                    success=True,
                )
                
                logger.info(
                    "rollback_executed",
                    fragment_id=fragment_id,
                    previous_version=previous_version_num,
                    target_version=target_version_num,
                    strategy=strategy.value,
                )
            else:
                # No rollback possible
                record = RollbackRecord(
                    rollback_id=rollback_id,
                    fragment_id=UUID(fragment_id) if self._is_valid_uuid(fragment_id) else uuid4(),
                    previous_version=previous_version_num,
                    target_version=previous_version_num,
                    trigger=strategy.value,
                    executed_at=executed_at,
                    success=False,
                    error_message="No target version available for rollback",
                )
                
                logger.warning(
                    "rollback_failed_no_target",
                    fragment_id=fragment_id,
                )
            
        except Exception as e:
            record = RollbackRecord(
                rollback_id=rollback_id,
                fragment_id=UUID(fragment_id) if self._is_valid_uuid(fragment_id) else uuid4(),
                previous_version=0,
                target_version=0,
                trigger=strategy.value,
                executed_at=executed_at,
                success=False,
                error_message=str(e),
            )
            
            logger.error(
                "rollback_execution_failed",
                fragment_id=fragment_id,
                error=str(e),
            )
        
        # Record the rollback attempt
        self._rollback_history.append(record)
        
        return record
    
    async def _determine_target_version(
        self,
        fragment_id: str,
        strategy: RollbackStrategy,
        versioning_service,
    ) -> int | None:
        """Determine which version to rollback to."""
        
        if strategy == RollbackStrategy.RESTORE_LAST_VALID:
            # Try safe version first
            if fragment_id in self._safe_versions:
                return self._safe_versions[fragment_id]
            
            # Otherwise get previous version
            versions = versioning_service.get_versions(fragment_id)
            active = versioning_service.get_active_version(fragment_id)
            
            if active and active.version_number > 1:
                return active.version_number - 1
            
            return None
            
        elif strategy == RollbackStrategy.RESTORE_PREVIOUS_VERSION:
            active = versioning_service.get_active_version(fragment_id)
            if active and active.version_number > 1:
                return active.version_number - 1
            return None
            
        elif strategy == RollbackStrategy.FALLBACK_TO_SAFE:
            return self._safe_versions.get(fragment_id)
            
        elif strategy == RollbackStrategy.CREATE_NEW_VERSION:
            # Don't rollback, just mark current as unsafe
            return None
        
        return None
    
    def _is_valid_uuid(self, value: str) -> bool:
        """Check if string is a valid UUID."""
        try:
            UUID(value)
            return True
        except (ValueError, AttributeError):
            return False
    
    def mark_safe_version(self, fragment_id: str, version_number: int) -> None:
        """Mark a version as safe (known to work correctly)."""
        self._safe_versions[fragment_id] = version_number
        logger.debug("safe_version_marked", fragment_id=fragment_id, version=version_number)
    
    def get_rollback_history(
        self,
        fragment_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get rollback history, optionally filtered by fragment."""
        history = self._rollback_history
        
        if fragment_id:
            history = [r for r in history if str(r.fragment_id) == fragment_id]
        
        # Sort by most recent
        history = sorted(history, key=lambda r: r.executed_at, reverse=True)
        
        return [
            {
                "rollback_id": str(r.rollback_id),
                "fragment_id": str(r.fragment_id),
                "previous_version": r.previous_version,
                "target_version": r.target_version,
                "trigger": r.trigger,
                "executed_at": r.executed_at.isoformat(),
                "success": r.success,
                "error_message": r.error_message,
            }
            for r in history[:limit]
        ]
    
    def get_rollback_stats(self) -> dict[str, Any]:
        """Get rollback statistics."""
        total = len(self._rollback_history)
        successful = sum(1 for r in self._rollback_history if r.success)
        failed = total - successful
        
        return {
            "total_rollbacks": total,
            "successful_rollbacks": successful,
            "failed_rollbacks": failed,
            "success_rate": round(successful / total, 3) if total > 0 else 0.0,
            "safe_versions_tracked": len(self._safe_versions),
        }
    
    def configure(
        self,
        max_retries_before_rollback: int | None = None,
        failure_threshold: float | None = None,
    ) -> None:
        """Configure rollback behavior."""
        if max_retries_before_rollback is not None:
            self._max_retries_before_rollback = max_retries_before_rollback
        if failure_threshold is not None:
            self._failure_threshold = max(0.0, min(1.0, failure_threshold))
        
        logger.info(
            "rollback_config_updated",
            max_retries=self._max_retries_before_rollback,
            failure_threshold=self._failure_threshold,
        )


# Singleton instance
_rollback_service: RollbackService | None = None


def get_rollback_service() -> RollbackService:
    """Get or create the rollback service singleton."""
    global _rollback_service
    if _rollback_service is None:
        _rollback_service = RollbackService()
    return _rollback_service