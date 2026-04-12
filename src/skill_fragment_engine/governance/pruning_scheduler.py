"""Pruning Scheduler - removes obsolete fragments."""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from typing import TYPE_CHECKING

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.governance.decay_manager import DecayManager

if TYPE_CHECKING:
    from skill_fragment_engine.core.models import SkillFragment

logger = structlog.get_logger(__name__)


class PruningScheduler:
    """
    Schedules and executes pruning of fragments.

    Removes:
    - Decayed fragments (below threshold)
    - Duplicates (high similarity, keep best)
    - Stale fragments (never used, old)
    - Low quality fragments
    - High failure rate fragments
    """

    def __init__(
        self,
        decay_manager: DecayManager | None = None,
    ):
        self.decay_manager = decay_manager or DecayManager()
        self.settings = get_settings()

    def run_pruning_cycle(
        self,
        fragments: list[SkillFragment],
        delete_callback=None,
    ) -> PruningReport:
        """
        Execute full pruning cycle.

        Args:
            fragments: List of all fragments
            delete_callback: Optional callback(fragment) called before deletion

        Returns:
            PruningReport with statistics
        """
        report = PruningReport()

        # 1. Decay-based pruning
        report.decay_removals = self._prune_by_decay(fragments, delete_callback)

        # 2. Duplicate detection
        report.duplicate_removals = self._prune_duplicates(fragments, delete_callback)

        # 3. Stale cleanup
        report.stale_removals = self._prune_stale(fragments, delete_callback)

        # 4. Low quality
        report.low_quality_removals = self._prune_low_quality(
            fragments, delete_callback
        )

        # 5. High failure rate
        report.failure_removals = self._prune_by_failure_rate(
            fragments, delete_callback
        )

        logger.info(
            "pruning_cycle_complete",
            total_removed=report.total_removed,
            decay=report.decay_removals,
            duplicates=report.duplicate_removals,
            stale=report.stale_removals,
            low_quality=report.low_quality_removals,
            failures=report.failure_removals,
        )

        return report

    def _prune_by_decay(
        self,
        fragments: list[SkillFragment],
        delete_callback=None,
    ) -> int:
        """Remove fragments below decay threshold."""
        removed = 0

        for fragment in fragments[:]:  # Copy list to allow modification
            if not fragment.is_active:
                continue

            if self.decay_manager.should_prune(fragment):
                if delete_callback:
                    delete_callback(fragment)
                fragments.remove(fragment)
                removed += 1

        return removed

    def _prune_duplicates(
        self,
        fragments: list[SkillFragment],
        delete_callback=None,
    ) -> int:
        """
        Find and remove duplicate fragments.

        Groups by task_type and input hash prefix,
        keeps the one with best score.
        """
        from collections import defaultdict

        removed = 0

        # Group by task type
        by_type: dict = defaultdict(list)
        for f in fragments:
            if f.is_active:
                by_type[f.task_type].append(f)

        for task_type, type_fragments in by_type.items():
            # Group by hash prefix (first 8 chars)
            by_hash: dict = defaultdict(list)
            for f in type_fragments:
                hash_prefix = f.input_signature.prompt_hash[:8]
                by_hash[hash_prefix].append(f)

            for hash_group in by_hash.values():
                if len(hash_group) < 2:
                    continue

                # Sort by score (descending)
                ranked = sorted(
                    hash_group,
                    key=lambda f: (
                        f.decay_score,
                        f.metrics.total_uses,
                        -f.metrics.failure_count,
                    ),
                    reverse=True,
                )

                # Remove all but best
                for duplicate in ranked[1:]:
                    if delete_callback:
                        delete_callback(duplicate)
                    fragments.remove(duplicate)
                    removed += 1

        return removed

    def _prune_stale(
        self,
        fragments: list[SkillFragment],
        delete_callback=None,
    ) -> int:
        """Remove fragments that are old and never used."""
        from datetime import datetime, timedelta, timezone

        removed = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        for fragment in fragments[:]:
            if not fragment.is_active:
                continue

            # Check if old and never used
            if (
                fragment.created_at < cutoff
                and fragment.metrics.total_uses == 0
            ):
                if delete_callback:
                    delete_callback(fragment)
                fragments.remove(fragment)
                removed += 1

        return removed

    def _prune_low_quality(
        self,
        fragments: list[SkillFragment],
        delete_callback=None,
        threshold: float = 0.3,
    ) -> int:
        """Remove fragments with very low quality score."""
        removed = 0

        for fragment in fragments[:]:
            if not fragment.is_active:
                continue

            if fragment.quality_score < threshold:
                if delete_callback:
                    delete_callback(fragment)
                fragments.remove(fragment)
                removed += 1

        return removed

    def _prune_by_failure_rate(
        self,
        fragments: list[SkillFragment],
        delete_callback=None,
        threshold: float = 0.1,
    ) -> int:
        """Remove fragments with high failure rate."""
        removed = 0

        for fragment in fragments[:]:
            if not fragment.is_active:
                continue

            total = fragment.metrics.total_uses + fragment.metrics.failure_count
            if total < 5:  # Need minimum sample size
                continue

            failure_rate = fragment.metrics.failure_count / total
            if failure_rate > threshold:
                if delete_callback:
                    delete_callback(fragment)
                fragments.remove(fragment)
                removed += 1

        return removed


@dataclass
class PruningReport:
    """Report from pruning cycle."""

    decay_removals: int = 0
    duplicate_removals: int = 0
    stale_removals: int = 0
    low_quality_removals: int = 0
    failure_removals: int = 0

    @property
    def total_removed(self) -> int:
        """Total fragments removed."""
        return (
            self.decay_removals
            + self.duplicate_removals
            + self.stale_removals
            + self.low_quality_removals
            + self.failure_removals
        )

    def __str__(self) -> str:
        return (
            f"PruningReport(total={self.total_removed}, "
            f"decay={self.decay_removals}, "
            f"duplicates={self.duplicate_removals}, "
            f"stale={self.stale_removals}, "
            f"low_quality={self.low_quality_removals}, "
            f"failures={self.failure_removals})"
        )
