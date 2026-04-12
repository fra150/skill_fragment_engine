"""Feedback service for handling user feedback and fragment scoring."""

from __future__ import annotations
import structlog
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from skill_fragment_engine.core.enums import (
    FeedbackType,
    FeedbackCategory,
    UserFeedback,
)
from skill_fragment_engine.core.config import get_settings, get_task_thresholds

logger = structlog.get_logger(__name__)


class FeedbackService:
    """
    Service for managing user feedback and fragment scoring.
    
    Features:
    - Store and retrieve feedback
    - Calculate fragment quality scores
    - Adjust thresholds based on feedback
    - Provide feedback statistics
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._feedback_store: list[UserFeedback] = []
        
        # Adaptive threshold configuration
        self._threshold_adjustment: dict[str, dict] = defaultdict(lambda: {
            "exact_match": 0.0,
            "adapt_match": 0.0,
            "sample_size": 0,
        })
        
        # Minimum samples before adjusting thresholds
        self._min_samples_for_adjustment = 10
    
    async def add_feedback(self, feedback: UserFeedback) -> UserFeedback:
        """
        Add user feedback and update fragment scores.
        
        Args:
            feedback: UserFeedback instance
            
        Returns:
            The stored feedback with updated ID
        """
        # Validate feedback
        if not feedback.feedback_type or not feedback.score:
            raise ValueError("Feedback must have type and score")
        
        feedback.feedback_id = feedback.feedback_id or uuid4()
        feedback.created_at = feedback.created_at or datetime.now(timezone.utc)
        
        # Store feedback
        self._feedback_store.append(feedback)
        
        logger.info(
            "feedback_received",
            feedback_id=str(feedback.feedback_id),
            fragment_id=str(feedback.fragment_id) if feedback.fragment_id else None,
            feedback_type=feedback.feedback_type.value,
            score=feedback.score,
        )
        
        # Process feedback for fragment scoring
        if feedback.fragment_id:
            await self._update_fragment_score(feedback)
        
        # Update threshold adjustments if enough samples
        if feedback.fragment_id:
            self._update_threshold_adjustments(feedback)
        
        return feedback
    
    async def get_feedback_for_fragment(self, fragment_id: str) -> list[UserFeedback]:
        """Get all feedback for a specific fragment."""
        return [f for f in self._feedback_store if str(f.fragment_id) == str(fragment_id)]
    
    async def get_feedback_stats(self, fragment_id: str | None = None) -> dict[str, Any]:
        """Get feedback statistics."""
        if fragment_id:
            feedback_list = await self.get_feedback_for_fragment(fragment_id)
        else:
            feedback_list = self._feedback_store
        
        if not feedback_list:
            return {
                "total_feedback": 0,
                "average_score": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
            }
        
        total = len(feedback_list)
        avg_score = sum(f.score for f in feedback_list) / total
        
        positive = sum(1 for f in feedback_list if f.feedback_type == FeedbackType.POSITIVE)
        negative = sum(1 for f in feedback_list if f.feedback_type == FeedbackType.NEGATIVE)
        neutral = sum(1 for f in feedback_list if f.feedback_type == FeedbackType.NEUTRAL)
        
        # Category breakdown
        category_counts = defaultdict(int)
        for f in feedback_list:
            category_counts[f.category.value] += 1
        
        return {
            "total_feedback": total,
            "average_score": round(avg_score, 3),
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "category_breakdown": dict(category_counts),
            "positive_ratio": round(positive / total, 3) if total > 0 else 0,
            "negative_ratio": round(negative / total, 3) if total > 0 else 0,
        }
    
    async def get_fragment_quality_score(self, fragment_id: str) -> float:
        """
        Get the quality score for a fragment based on feedback.
        
        Returns a weighted score where:
        - Recent feedback has more weight
        - Positive feedback increases score
        - Negative feedback decreases score
        - Neutral feedback has minimal impact
        """
        feedback_list = await self.get_feedback_for_fragment(fragment_id)
        
        if not feedback_list:
            return 0.5  # Default score
        
        # Weight by recency (last 30 days have full weight, older have reduced weight)
        now = datetime.now(timezone.utc)
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for f in feedback_list:
            age_days = (now - f.created_at).days
            recency_weight = max(0.1, 1.0 - (age_days / 90))  # Decay over 90 days
            
            # Score weight based on feedback type
            if f.feedback_type == FeedbackType.POSITIVE:
                type_weight = 1.0
            elif f.feedback_type == FeedbackType.NEGATIVE:
                type_weight = -1.0
            else:
                type_weight = 0.0
            
            weighted_sum += f.score * type_weight * recency_weight
            weight_sum += recency_weight
        
        if weight_sum == 0:
            return 0.5
        
        # Normalize to 0-1 range with center at 0.5
        normalized = 0.5 + (weighted_sum / (weight_sum * 2))
        return max(0.0, min(1.0, normalized))
    
    async def _update_fragment_score(self, feedback: UserFeedback) -> None:
        """Update fragment's quality score based on feedback."""
        if not feedback.fragment_id:
            return
        
        logger.debug(
            "updating_fragment_score",
            fragment_id=str(feedback.fragment_id),
            score=feedback.score,
        )
    
    def _update_threshold_adjustments(self, feedback: UserFeedback) -> None:
        """Update threshold adjustments based on feedback patterns."""
        if not feedback.fragment_id:
            return
        
        # Determine task type from fragment or use default
        task_type = "code_generation"  # Default, would come from fragment in production
        
        adj = self._threshold_adjustment[task_type]
        adj["sample_size"] += 1
        
        if adj["sample_size"] < self._min_samples_for_adjustment:
            return
        
        # Adjust thresholds based on feedback patterns
        # If negative feedback is high, increase thresholds (be more strict)
        # If positive feedback is high, decrease thresholds (be more lenient)
        
        recent_feedback = [
            f for f in self._feedback_store 
            if str(f.fragment_id) == str(feedback.fragment_id)
            and (datetime.now(timezone.utc) - f.created_at).days < 30
        ]
        
        if len(recent_feedback) < 5:
            return
        
        neg_ratio = sum(1 for f in recent_feedback if f.feedback_type == FeedbackType.NEGATIVE) / len(recent_feedback)
        
        if neg_ratio > 0.3:
            # More than 30% negative - increase thresholds (be more strict)
            adjustment = min(0.05, (neg_ratio - 0.3) * 0.1)
            adj["exact_match"] = adjustment
            adj["adapt_match"] = adjustment * 0.5
            logger.info("thresholds_increased", task_type=task_type, adjustment=adjustment)
        elif neg_ratio < 0.1:
            # Less than 10% negative - decrease thresholds (be more lenient)
            adjustment = -min(0.05, (0.1 - neg_ratio) * 0.1)
            adj["exact_match"] = adjustment
            adj["adapt_match"] = adjustment * 0.5
            logger.info("thresholds_decreased", task_type=task_type, adjustment=adjustment)
    
    def get_adjusted_thresholds(self, task_type: str) -> dict[str, float]:
        """
        Get task-type specific thresholds adjusted based on feedback.
        
        Returns:
            Dict with 'exact_match' and 'adapt_match' adjusted values
        """
        base_thresholds = get_task_thresholds(task_type)
        
        adj = self._threshold_adjustment.get(task_type, {})
        
        if adj.get("sample_size", 0) < self._min_samples_for_adjustment:
            return {
                "exact_match": base_thresholds.exact_match,
                "adapt_match": base_thresholds.adapt_match,
            }
        
        return {
            "exact_match": base_thresholds.exact_match + adj.get("exact_match", 0.0),
            "adapt_match": base_thresholds.adapt_match + adj.get("adapt_match", 0.0),
        }
    
    async def get_recent_feedback(
        self,
        limit: int = 50,
        feedback_type: FeedbackType | None = None,
    ) -> list[UserFeedback]:
        """Get recent feedback, optionally filtered by type."""
        sorted_feedback = sorted(
            self._feedback_store, 
            key=lambda f: f.created_at, 
            reverse=True
        )
        
        if feedback_type:
            sorted_feedback = [f for f in sorted_feedback if f.feedback_type == feedback_type]
        
        return sorted_feedback[:limit]
    
    async def clear_old_feedback(self, days_old: int = 90) -> int:
        """Clear feedback older than specified days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        original_count = len(self._feedback_store)
        
        self._feedback_store = [
            f for f in self._feedback_store 
            if f.created_at > cutoff
        ]
        
        cleared = original_count - len(self._feedback_store)
        
        if cleared > 0:
            logger.info("old_feedback_cleared", count=cleared, days_old=days_old)
        
        return cleared


# Singleton instance
_feedback_service: FeedbackService | None = None


def get_feedback_service() -> FeedbackService:
    """Get or create the feedback service singleton."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service
