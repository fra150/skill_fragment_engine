"""Scoring Calculator - ranks fragments by quality."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from skill_fragment_engine.core.config import get_settings

if TYPE_CHECKING:
    from skill_fragment_engine.core.models import SkillFragment

logger = structlog.get_logger(__name__)


class ScoringCalculator:
    """
    Calculates composite scores for fragment ranking.

    Combines multiple factors:
    - Decay score (freshness)
    - Reuse rate
    - Quality trend
    - Recency
    - Adaptability
    """

    # Weights for scoring components
    WEIGHTS = {
        "decay": 0.25,
        "reuse_rate": 0.25,
        "quality": 0.20,
        "recency": 0.15,
        "adaptability": 0.15,
    }

    def __init__(self):
        self.settings = get_settings()

    def calculate_fragment_score(self, fragment: SkillFragment) -> float:
        """
        Calculate overall fragment score (0.0 - 1.0).

        Args:
            fragment: Fragment to score

        Returns:
            Composite score
        """
        if not fragment.is_active:
            return 0.0

        # Component scores
        scores = {
            "decay": self._score_decay(fragment),
            "reuse_rate": self._score_reuse_rate(fragment),
            "quality": self._score_quality(fragment),
            "recency": self._score_recency(fragment),
            "adaptability": self._score_adaptability(fragment),
        }

        # Weighted sum
        total = sum(
            self.WEIGHTS[component] * scores[component]
            for component in self.WEIGHTS
        )

        return round(total, 4)

    def _score_decay(self, fragment: SkillFragment) -> float:
        """Score based on decay score."""
        return fragment.decay_score

    def _score_reuse_rate(self, fragment: SkillFragment) -> float:
        """
        Score based on reuse rate.

        Higher reuse = better.
        """
        total_uses = fragment.metrics.total_uses
        total = total_uses + fragment.metrics.failure_count
        if total == 0:
            return 0.5  # Neutral for never-used fragments

        reuse_rate = total_uses / total
        usage_score = min(1.0, math.log1p(total_uses) / math.log1p(100))
        return (reuse_rate + usage_score) / 2

    def _score_quality(self, fragment: SkillFragment) -> float:
        """Score based on quality assessment."""
        return fragment.quality_score

    def _score_recency(self, fragment: SkillFragment) -> float:
        """
        Score based on recency of last use.

        Recently used = higher score.
        """
        if not fragment.validation_history:
            # No usage history - use creation date
             age_days = (datetime.now(timezone.utc) - fragment.created_at).days
        else:
             # Use last validation date
             last_use = max(v.timestamp for v in fragment.validation_history)
             age_days = (datetime.now(timezone.utc) - last_use).days

        # Exponential decay over 90 days
        if age_days <= 0:
            return 1.0

        recency = 0.5 ** (age_days / 90)
        return max(0.0, min(1.0, recency))

    def _score_adaptability(self, fragment: SkillFragment) -> float:
        """
        Score based on adaptability.

        Fragments that work for multiple contexts = better.
        High adaptation count with low failure = ideal.
        """
        reuse = fragment.metrics.reuse_count
        adapt = fragment.metrics.adapt_count
        fail = fragment.metrics.failure_count

        total = reuse + adapt + fail
        if total == 0:
            return 0.5  # Neutral

        # Ideal: high reuse, low adaptation (works as-is)
        # Adaptation is good if it succeeds
        success_rate = (reuse + adapt) / total if total > 0 else 0

        # Bonus for successful adaptations
        adaptation_bonus = adapt / (total * 2) if adapt > 0 else 0

        return min(1.0, success_rate + adaptation_bonus)

    def rank_fragments(
        self,
        fragments: list[SkillFragment],
        top_k: int | None = None,
    ) -> list[SkillFragment]:
        """
        Rank fragments by composite score.

        Args:
            fragments: Fragments to rank
            top_k: Return only top K (None = all)

        Returns:
            Sorted list of fragments
        """
        # Calculate scores and sort
        scored = [
            (f, self.calculate_fragment_score(f))
            for f in fragments
            if f.is_active
        ]

        ranked = sorted(scored, key=lambda x: x[1], reverse=True)

        result = [f for f, _ in ranked]

        if top_k is not None:
            result = result[:top_k]

        return result

    def get_top_for_task_type(
        self,
        fragments: list[SkillFragment],
        task_type: str,
        top_k: int = 10,
    ) -> list[SkillFragment]:
        """
        Get top fragments for a specific task type.

        Args:
            fragments: All fragments
            task_type: Task type to filter
            top_k: Number to return

        Returns:
            Top K fragments for task type
        """
        filtered = [f for f in fragments if f.task_type == task_type and f.is_active]
        return self.rank_fragments(filtered, top_k=top_k)

    def calculate_quality_trend(self, fragment: SkillFragment) -> float:
        """
        Calculate quality trend based on recent validations.

        Returns:
            Trend score: positive (improving), 0 (stable), negative (degrading)
        """
        history = fragment.validation_history

        if len(history) < 3:
            return 0.0  # Not enough data

        # Compare recent vs older validations
        recent = history[-3:]
        older = history[:-3]

        if not older:
            return 0.0

        # Success rate calculation
        recent_success = sum(
            1 for v in recent
            if v.outcome.value in ("reused_successfully", "adapted")
        ) / len(recent)

        older_success = sum(
            1 for v in older
            if v.outcome.value in ("reused_successfully", "adapted")
        ) / len(older)

        # Trend: recent - older
        trend = recent_success - older_success

        # Clamp to -1, 1
        return max(-1.0, min(1.0, trend))
