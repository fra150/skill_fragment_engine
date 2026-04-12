"""Decay Manager - skill fragments lose weight over time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import structlog

from skill_fragment_engine.core.config import THRESHOLDS_CONFIG, TaskTypeThresholds, get_settings

if TYPE_CHECKING:
    from skill_fragment_engine.core.models import SkillFragment

logger = structlog.get_logger(__name__)


class DecayManager:
    """
    Manages decay of skill fragments over time.

    Fragments lose "weight" (decay_score) as they age.
    Recent usage slows decay. Very old fragments are deactivated.
    """

    def __init__(self):
        self.settings = get_settings()

    def _as_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def calculate_decay_score(self, fragment: SkillFragment) -> float:
        """
        Calculate current decay score for a fragment.

        Uses exponential decay based on age, with usage boost.

        Args:
            fragment: Fragment to calculate decay for

        Returns:
            Decay score between 0.0 and 1.0
        """
        task_type = fragment.task_type.value if hasattr(fragment.task_type, "value") else str(fragment.task_type)
        thresholds = self._get_thresholds(task_type)

        # Time-based decay (exponential)
        created_at = self._as_utc(fragment.created_at)
        age_days = (datetime.now(timezone.utc) - created_at).days
        half_life = thresholds.half_life_days

        # Exponential decay: score = 0.5 ^ (age / half_life)
        if age_days <= 0:
            time_factor = 1.0
        else:
            time_factor = 0.5 ** (age_days / half_life)

        # Usage-based boost
        usage_factor = self._calculate_usage_factor(fragment)

        # Combine with weights
        base_weight = 1.0 - thresholds.min_decay_threshold
        final_score = (
            time_factor * base_weight
            + thresholds.min_decay_threshold
            + usage_factor * thresholds.min_decay_threshold
        )

        # Clamp to valid range
        final_score = max(
            thresholds.min_decay_threshold,
            min(1.0, final_score)
        )

        return round(final_score, 4)

    def _calculate_usage_factor(self, fragment: SkillFragment) -> float:
        """
        Calculate usage-based boost factor.

        Recently used fragments decay slower.
        """
        # Count uses in last 30 days
        recent_uses = self._count_recent_uses(fragment, days=30)

        # Usage boost: up to 30% based on usage
        usage_factor = min(1.0, recent_uses / 10) * 0.3

        return usage_factor

    def _count_recent_uses(self, fragment: SkillFragment, days: int = 30) -> int:
        """Count fragment uses in the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent_validations = [
            v for v in fragment.validation_history
            if self._as_utc(v.timestamp) > cutoff
        ]

        return len(recent_validations)

    def _get_thresholds(self, task_type: str) -> TaskTypeThresholds:
        """Get thresholds for task type."""
        return THRESHOLDS_CONFIG.get(
            task_type,
            TaskTypeThresholds()
        )

    def apply_decay(
        self,
        fragments: list[SkillFragment],
        update_callback=None,
    ) -> DecayReport:
        """
        Apply decay to all fragments.

        Args:
            fragments: List of fragments to process
            update_callback: Optional callback(fragment, old_score, new_score)

        Returns:
            DecayReport with statistics
        """
        report = DecayReport()
        now = datetime.now(timezone.utc)

        for fragment in fragments:
            if not fragment.is_active:
                continue

            old_score = fragment.decay_score
            new_score = self.calculate_decay_score(fragment)

            if old_score != new_score:
                fragment.decay_score = new_score
                fragment.updated_at = now
                report.updated += 1

                if update_callback:
                    update_callback(fragment, old_score, new_score)

            # Check for deactivation
            task_type = (
                fragment.task_type.value
                if hasattr(fragment.task_type, "value")
                else str(fragment.task_type)
            )
            thresholds = self._get_thresholds(task_type)
            if new_score < thresholds.min_decay_threshold:
                fragment.is_active = False
                report.deactivated += 1
                logger.info(
                    "fragment_deactivated",
                    fragment_id=fragment.fragment_id,
                    decay_score=new_score,
                    threshold=thresholds.min_decay_threshold,
                )

        logger.info(
            "decay_cycle_complete",
            total=len(fragments),
            updated=report.updated,
            deactivated=report.deactivated,
        )

        return report

    def should_prune(self, fragment: SkillFragment) -> bool:
        """
        Check if fragment should be pruned based on decay.

        Args:
            fragment: Fragment to check

        Returns:
            True if fragment should be removed
        """
        task_type = fragment.task_type.value if hasattr(fragment.task_type, "value") else str(fragment.task_type)
        thresholds = self._get_thresholds(task_type)

        created_at = self._as_utc(fragment.created_at)
        age_days = (datetime.now(timezone.utc) - created_at).days
        if age_days < 7:  # Minimum 7 days old
            return False

        # Check decay threshold
        if fragment.decay_score < thresholds.min_decay_threshold * 0.5:
            return True

        # Check failure rate
        total = fragment.metrics.total_uses + fragment.metrics.failure_count
        if total > 10:
            failure_rate = fragment.metrics.failure_count / total
            if failure_rate > 0.2:  # More than 20% failures
                return True

        # Check if never used and old
        if (
            fragment.metrics.total_uses == 0
            and age_days > 30
        ):
            return True

        return False


@dataclass
class DecayReport:
    """Report from decay cycle."""

    updated: int = 0
    deactivated: int = 0

    def __str__(self) -> str:
        return f"DecayReport(updated={self.updated}, deactivated={self.deactivated})"
