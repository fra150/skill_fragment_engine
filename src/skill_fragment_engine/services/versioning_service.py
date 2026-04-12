"""Versioning service for fragment version management."""

from __future__ import annotations

import structlog
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from skill_fragment_engine.core.enums import SkillFragment, Variant, ValidationResult
from skill_fragment_engine.core.config import get_settings

logger = structlog.get_logger(__name__)


class VersionInfo:
    """Information about a fragment version."""
    
    def __init__(
        self,
        version_id: UUID,
        version_number: int,
        created_at: datetime,
        created_from: str,
        parent_version_id: UUID | None = None,
        changelog: str = "",
        is_active: bool = True,
        is_deprecated: bool = False,
        deprecation_reason: str | None = None,
        deprecated_at: datetime | None = None,
    ):
        self.version_id = version_id
        self.version_number = version_number
        self.created_at = created_at
        self.created_from = created_from
        self.parent_version_id = parent_version_id
        self.changelog = changelog
        self.is_active = is_active
        self.is_deprecated = is_deprecated
        self.deprecation_reason = deprecation_reason
        self.deprecated_at = deprecated_at


class BranchInfo:
    """Information about a fragment branch."""
    
    def __init__(
        self,
        branch_id: UUID,
        branch_name: str,
        base_version_id: UUID,
        created_at: datetime,
        created_by: str | None = None,
        is_default: bool = False,
    ):
        self.branch_id = branch_id
        self.branch_name = branch_name
        self.base_version_id = base_version_id
        self.created_at = created_at
        self.created_by = created_by
        self.is_default = is_default


class VersioningService:
    """
    Service for managing fragment versions, branches, and rollback.
    
    Features:
    - Version numbering and tracking
    - Branch creation and merging
    - Deprecation management
    - Rollback capabilities
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Storage for versions and branches (in production, this would be a database)
        self._versions: dict[str, list[VersionInfo]] = {}  # fragment_id -> versions
        self._branches: dict[str, list[BranchInfo]] = {}  # fragment_id -> branches
        self._active_version: dict[str, UUID] = {}  # fragment_id -> active version_id
    
    def create_initial_version(
        self,
        fragment: SkillFragment,
        created_by: str | None = None,
    ) -> VersionInfo:
        """
        Create the initial version for a new fragment.
        
        Args:
            fragment: The fragment to version
            created_by: Optional creator identifier
            
        Returns:
            VersionInfo for the initial version
        """
        version_id = uuid4()
        version = VersionInfo(
            version_id=version_id,
            version_number=1,
            created_at=datetime.utcnow(),
            created_from="creation",
            parent_version_id=None,
            changelog="Initial version created",
            is_active=True,
            is_deprecated=False,
        )
        
        # Store version
        fragment_id = str(fragment.fragment_id)
        if fragment_id not in self._versions:
            self._versions[fragment_id] = []
        self._versions[fragment_id].append(version)
        
        # Set as active version
        self._active_version[fragment_id] = version_id
        
        # Create default branch
        default_branch = BranchInfo(
            branch_id=uuid4(),
            branch_name="main",
            base_version_id=version_id,
            created_at=datetime.utcnow(),
            created_by=created_by,
            is_default=True,
        )
        
        if fragment_id not in self._branches:
            self._branches[fragment_id] = []
        self._branches[fragment_id].append(default_branch)
        
        logger.info(
            "version_created",
            fragment_id=fragment_id,
            version_id=str(version_id),
            version_number=1,
        )
        
        return version
    
    def create_new_version(
        self,
        fragment_id: str,
        created_from: str,
        parent_version_id: UUID | None = None,
        changelog: str = "",
        created_by: str | None = None,
    ) -> VersionInfo:
        """
        Create a new version of an existing fragment.
        
        Args:
            fragment_id: ID of the fragment
            created_from: Reason for new version (adaptation, improvement, etc.)
            parent_version_id: Parent version ID (defaults to active)
            changelog: Description of changes
            created_by: Optional creator identifier
            
        Returns:
            VersionInfo for the new version
        """
        # Get current versions
        versions = self._versions.get(fragment_id, [])
        
        # Determine parent version
        if parent_version_id is None:
            parent_version_id = self._active_version.get(fragment_id)
        
        # Calculate new version number
        if versions:
            max_version = max(v.version_number for v in versions)
            new_version_number = max_version + 1
        else:
            new_version_number = 1
        
        # Create new version
        version_id = uuid4()
        version = VersionInfo(
            version_id=version_id,
            version_number=new_version_number,
            created_at=datetime.utcnow(),
            created_from=created_from,
            parent_version_id=parent_version_id,
            changelog=changelog,
            is_active=True,
            is_deprecated=False,
        )
        
        # Store version
        if fragment_id not in self._versions:
            self._versions[fragment_id] = []
        self._versions[fragment_id].append(version)
        
        # Deactivate parent if this is a full replacement
        if parent_version_id:
            for v in self._versions.get(fragment_id, []):
                if v.version_id == parent_version_id and created_from in ["improvement", "fix"]:
                    v.is_active = False
        
        # Set as active version
        self._active_version[fragment_id] = version_id
        
        logger.info(
            "new_version_created",
            fragment_id=fragment_id,
            version_id=str(version_id),
            version_number=new_version_number,
            parent_version_id=str(parent_version_id) if parent_version_id else None,
        )
        
        return version
    
    def create_branch(
        self,
        fragment_id: str,
        branch_name: str,
        base_version_id: UUID | None = None,
        created_by: str | None = None,
    ) -> BranchInfo:
        """
        Create a new branch from an existing version.
        
        Args:
            fragment_id: ID of the fragment
            branch_name: Name for the new branch
            base_version_id: Version to branch from (defaults to active)
            created_by: Optional creator identifier
            
        Returns:
            BranchInfo for the new branch
        """
        # Determine base version
        if base_version_id is None:
            base_version_id = self._active_version.get(fragment_id)
        
        if base_version_id is None:
            raise ValueError(f"No active version found for fragment {fragment_id}")
        
        # Create branch
        branch_id = uuid4()
        branch = BranchInfo(
            branch_id=branch_id,
            branch_name=branch_name,
            base_version_id=base_version_id,
            created_at=datetime.utcnow(),
            created_by=created_by,
            is_default=False,
        )
        
        # Store branch
        if fragment_id not in self._branches:
            self._branches[fragment_id] = []
        self._branches[fragment_id].append(branch)
        
        logger.info(
            "branch_created",
            fragment_id=fragment_id,
            branch_id=str(branch_id),
            branch_name=branch_name,
            base_version_id=str(base_version_id),
        )
        
        return branch
    
    def merge_branch(
        self,
        fragment_id: str,
        source_branch_name: str,
        target_branch_name: str = "main",
        merge_strategy: str = "replace",
        created_by: str | None = None,
    ) -> VersionInfo:
        """
        Merge a branch into another branch.
        
        Args:
            fragment_id: ID of the fragment
            source_branch_name: Branch to merge from
            target_branch_name: Branch to merge into
            merge_strategy: Strategy for merge (replace, combine, keep_both)
            created_by: Optional creator identifier
            
        Returns:
            VersionInfo for the merge result
        """
        branches = self._branches.get(fragment_id, [])
        
        source_branch = next((b for b in branches if b.branch_name == source_branch_name), None)
        target_branch = next((b for b in branches if b.branch_name == target_branch_name), None)
        
        if not source_branch or not target_branch:
            raise ValueError(f"Branch not found for fragment {fragment_id}")
        
        # Get source version
        versions = self._versions.get(fragment_id, [])
        source_version = next((v for v in versions if v.version_id == source_branch.base_version_id), None)
        
        if not source_version:
            raise ValueError(f"Source version not found")
        
        # Create merge version
        if merge_strategy == "keep_both":
            # Create new version with incremented number
            max_version = max((v.version_number for v in versions), default=0)
            new_version_number = max_version + 1
        else:
            # Replace target version
            new_version_number = source_version.version_number
        
        merge_version = self.create_new_version(
            fragment_id=fragment_id,
            created_from="merge",
            parent_version_id=target_branch.base_version_id,
            changelog=f"Merged from branch '{source_branch_name}' using '{merge_strategy}' strategy",
            created_by=created_by,
        )
        
        logger.info(
            "branch_merged",
            fragment_id=fragment_id,
            source_branch=source_branch_name,
            target_branch=target_branch_name,
            merge_strategy=merge_strategy,
            new_version_id=str(merge_version.version_id),
        )
        
        return merge_version
    
    def deprecate_version(
        self,
        fragment_id: str,
        version_number: int,
        reason: str,
        deprecated_by: str | None = None,
    ) -> bool:
        """
        Deprecate a specific version of a fragment.
        
        Args:
            fragment_id: ID of the fragment
            version_number: Version number to deprecate
            reason: Reason for deprecation
            deprecated_by: Optional deprecator identifier
            
        Returns:
            True if successful
        """
        versions = self._versions.get(fragment_id, [])
        
        version = next((v for v in versions if v.version_number == version_number), None)
        
        if not version:
            raise ValueError(f"Version {version_number} not found for fragment {fragment_id}")
        
        version.is_deprecated = True
        version.deprecation_reason = reason
        version.deprecated_at = datetime.utcnow()
        version.is_active = False
        
        logger.info(
            "version_deprecated",
            fragment_id=fragment_id,
            version_number=version_number,
            reason=reason,
        )
        
        return True
    
    def rollback_to_version(
        self,
        fragment_id: str,
        version_number: int,
        reason: str = "",
    ) -> VersionInfo:
        """
        Rollback to a specific version of a fragment.
        
        Args:
            fragment_id: ID of the fragment
            version_number: Version number to rollback to
            reason: Reason for rollback
            
        Returns:
            VersionInfo for the rollback version
        """
        versions = self._versions.get(fragment_id, [])
        
        target_version = next((v for v in versions if v.version_number == version_number), None)
        
        if not target_version:
            raise ValueError(f"Version {version_number} not found for fragment {fragment_id}")
        
        # Create a new version that's a copy of the target
        rollback_version = self.create_new_version(
            fragment_id=fragment_id,
            created_from="rollback",
            parent_version_id=self._active_version.get(fragment_id),
            changelog=f"Rolled back to version {version_number}: {reason}" if reason else f"Rolled back to version {version_number}",
        )
        
        logger.info(
            "version_rollback",
            fragment_id=fragment_id,
            target_version=version_number,
            new_version=rollback_version.version_number,
        )
        
        return rollback_version
    
    def get_versions(self, fragment_id: str) -> list[VersionInfo]:
        """Get all versions for a fragment, sorted by version number."""
        versions = self._versions.get(fragment_id, [])
        return sorted(versions, key=lambda v: v.version_number, reverse=True)
    
    def get_active_version(self, fragment_id: str) -> VersionInfo | None:
        """Get the active version for a fragment."""
        active_id = self._active_version.get(fragment_id)
        if not active_id:
            return None
        
        versions = self._versions.get(fragment_id, [])
        return next((v for v in versions if v.version_id == active_id), None)
    
    def get_version(self, fragment_id: str, version_number: int) -> VersionInfo | None:
        """Get a specific version of a fragment."""
        versions = self._versions.get(fragment_id, [])
        return next((v for v in versions if v.version_number == version_number), None)
    
    def get_branches(self, fragment_id: str) -> list[BranchInfo]:
        """Get all branches for a fragment."""
        return self._branches.get(fragment_id, [])
    
    def get_version_history(
        self,
        fragment_id: str,
        include_deprecated: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get version history for a fragment.
        
        Args:
            fragment_id: ID of the fragment
            include_deprecated: Include deprecated versions
            
        Returns:
            List of version info dictionaries
        """
        versions = self.get_versions(fragment_id)
        
        if not include_deprecated:
            versions = [v for v in versions if not v.is_deprecated]
        
        return [
            {
                "version_id": str(v.version_id),
                "version_number": v.version_number,
                "created_at": v.created_at.isoformat(),
                "created_from": v.created_from,
                "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
                "changelog": v.changelog,
                "is_active": v.is_active,
                "is_deprecated": v.is_deprecated,
                "deprecation_reason": v.deprecation_reason,
                "deprecated_at": v.deprecated_at.isoformat() if v.deprecated_at else None,
            }
            for v in versions
        ]


# Singleton instance
_versioning_service: VersioningService | None = None


def get_versioning_service() -> VersioningService:
    """Get or create the versioning service singleton."""
    global _versioning_service
    if _versioning_service is None:
        _versioning_service = VersioningService()
    return _versioning_service