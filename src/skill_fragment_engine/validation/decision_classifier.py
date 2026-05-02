"""Decision classifier for validator engine."""

from dataclasses import dataclass

from skill_fragment_engine.core.config import TaskTypeThresholds, get_task_thresholds
from skill_fragment_engine.core.enums import Decision, TaskType
from skill_fragment_engine.core.models import SkillFragment, MatchCandidate


@dataclass
class DecisionInput:
    """Input for decision classification."""

    task_type: TaskType | str
    distance: float  # Context distance from comparison
    similarity_score: float  # Raw similarity from retrieval
    fragment: SkillFragment | None = None
    adaptation_cost_estimate: float | None = None
    recompute_cost: float | None = None
    allow_adaptation: bool = True
    allow_recompute: bool = True


@dataclass
class DecisionOutput:
    """Output from decision classification."""

    decision: Decision
    score: float  # Confidence in decision
    reason: str
    should_adapt: bool = False
    adaptation_cost_estimate: float | None = None


class DecisionClassifier:
    """
    Classifies retrieval decisions based on thresholds and costs.

    Implements the decision tree from SPEC.md:
    1. Exact match → REUSE
    2. Distance <= threshold.exact_match → REUSE
    3. Distance <= threshold.adapt_match and adaptation cheaper → ADAPT
    4. Otherwise → RECOMPUTE
    
    Optionally integrates with FeedbackService for adaptive thresholds
    based on user feedback patterns.
    """

    def __init__(self, use_adaptive_thresholds: bool = True):
        self._thresholds_cache: dict[str, TaskTypeThresholds] = {}
        self._use_adaptive_thresholds = use_adaptive_thresholds
        self._feedback_service = None
        
        # Cache for adaptive thresholds
        self._adaptive_thresholds: dict[str, dict] = {}
    
    def _get_feedback_service(self):
        """Lazy load feedback service to avoid circular imports."""
        if self._feedback_service is None and self._use_adaptive_thresholds:
            try:
                from skill_fragment_engine.services.feedback_service import get_feedback_service
                self._feedback_service = get_feedback_service()
            except ImportError:
                pass
        return self._feedback_service

    def classify(self, input_data: DecisionInput) -> DecisionOutput:
        """
        Classify the retrieval decision.

        Args:
            input_data: Decision input with thresholds and costs

        Returns:
            Decision output with action and confidence
        """
        task_type = (
            input_data.task_type.value
            if isinstance(input_data.task_type, TaskType)
            else input_data.task_type
        )

        thresholds = self._get_thresholds(task_type)

        # Case 1: Exact match (distance ~ 0)
        if input_data.distance <= 0.01 and input_data.similarity_score >= 0.99:
            return DecisionOutput(
                decision=Decision.REUSE,
                score=0.99,
                reason="Exact match on input signature",
            )

        # Case 2: Within exact match threshold
        if input_data.distance <= thresholds.exact_match:
            return DecisionOutput(
                decision=Decision.REUSE,
                score=self._compute_confidence(input_data.distance, thresholds.exact_match),
                reason=f"Within exact match threshold ({thresholds.exact_match})",
            )

        # Case 3: Within adaptation threshold
        if (
            input_data.distance <= thresholds.adapt_match
            and thresholds.adaptation_allowed
            and input_data.allow_adaptation
        ):
            # Check if adaptation is cost-effective
            if self._should_adapt(input_data):
                adaptation_cost = input_data.adaptation_cost_estimate or self._estimate_adaptation_cost(input_data)
                return DecisionOutput(
                    decision=Decision.ADAPT,
                    score=self._compute_confidence(input_data.distance, thresholds.adapt_match),
                    reason=f"Within adaptation threshold ({thresholds.adapt_match}), adaptation cost-effective",
                    should_adapt=True,
                    adaptation_cost_estimate=adaptation_cost,
                )
            else:
                # Adaptation available but not cost-effective
                return DecisionOutput(
                    decision=Decision.RECOMPUTE,
                    score=0.6,
                    reason="Adaptation available but not cost-effective compared to recompute",
                )

        # Case 4: Outside thresholds - check if adaptation is forced
        if input_data.allow_adaptation and thresholds.adaptation_allowed:
            # Could adapt but outside thresholds - still better than recompute?
            if input_data.distance <= thresholds.adapt_match * 1.5:
                adaptation_cost = input_data.adaptation_cost_estimate or self._estimate_adaptation_cost(input_data)
                recompute_cost = input_data.recompute_cost or self._get_default_recompute_cost(task_type)

                if adaptation_cost < recompute_cost * 0.5:
                    return DecisionOutput(
                        decision=Decision.ADAPT,
                        score=0.4,
                        reason="Partial adaptation may be beneficial",
                        should_adapt=True,
                        adaptation_cost_estimate=adaptation_cost,
                    )

        # Case 5: Default to recompute
        if input_data.allow_recompute:
            return DecisionOutput(
                decision=Decision.RECOMPUTE,
                score=0.7,
                reason=f"Outside all thresholds (distance={input_data.distance:.3f})",
            )

        # Case 6: No recompute allowed - must adapt if possible
        if thresholds.adaptation_allowed and input_data.allow_adaptation:
            return DecisionOutput(
                decision=Decision.ADAPT,
                score=0.3,
                reason="Forced adaptation (recompute disabled)",
                should_adapt=True,
            )

        # Case 7: Nowhere to go
        return DecisionOutput(
            decision=Decision.RECOMPUTE,
            score=0.1,
            reason="No valid path available",
        )

    def _get_thresholds(self, task_type: str) -> TaskTypeThresholds:
        """Get thresholds for task type, optionally adjusted by feedback."""
        if task_type not in self._thresholds_cache:
            self._thresholds_cache[task_type] = get_task_thresholds(task_type)
        
        base_thresholds = self._thresholds_cache[task_type]
        
        # If adaptive thresholds enabled, get adjustments from feedback
        if self._use_adaptive_thresholds:
            feedback_svc = self._get_feedback_service()
            if feedback_svc:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're in async context, we'll use sync fallback
                        adjusted = self._get_adjusted_thresholds_sync(task_type, base_thresholds)
                    else:
                        adjusted = asyncio.run(feedback_svc.get_adjusted_thresholds(task_type))
                    
                    # Return adjusted thresholds
                    from skill_fragment_engine.core.config import TaskTypeThresholds
                    return TaskTypeThresholds(
                        exact_match=adjusted["exact_match"],
                        adapt_match=adjusted["adapt_match"],
                        adaptation_allowed=base_thresholds.adaptation_allowed,
                        half_life_days=base_thresholds.half_life_days,
                        min_decay_threshold=base_thresholds.min_decay_threshold,
                    )
                except Exception as e:
                    # Fall back to base thresholds
                    import structlog
                    logger = structlog.get_logger(__name__)
                    logger.warning("adaptive_thresholds_failed", error=str(e))
        
        return base_thresholds
    
    def _get_adjusted_thresholds_sync(self, task_type: str, base: TaskTypeThresholds) -> dict:
        """Synchronous fallback for getting adjusted thresholds."""
        # Simple sync version - in production would be async
        return {
            "exact_match": base.exact_match,
            "adapt_match": base.adapt_match,
        }

    def _compute_confidence(self, distance: float, threshold: float) -> float:
        """Compute confidence score based on distance vs threshold."""
        if distance <= 0:
            return 1.0

        ratio = distance / threshold
        # Higher ratio = lower confidence
        confidence = max(0.0, 1.0 - ratio)
        return round(confidence, 3)

    def _should_adapt(self, input_data: DecisionInput) -> bool:
        """Determine if adaptation should be used."""
        adaptation_cost = input_data.adaptation_cost_estimate or 0.002
        recompute_cost = input_data.recompute_cost or 0.021

        # Adapt if it's significantly cheaper
        return adaptation_cost < recompute_cost * 0.5

    def _estimate_adaptation_cost(self, input_data: DecisionInput) -> float:
        """Estimate the cost of adaptation."""
        # Base adaptation cost
        base = 0.0021

        # Adjust based on distance
        thresholds = self._get_thresholds(
            input_data.task_type.value
            if isinstance(input_data.task_type, TaskType)
            else input_data.task_type
        )

        distance_ratio = input_data.distance / thresholds.adapt_match
        cost_multiplier = 1.0 + (distance_ratio - 1.0) * 0.5

        return round(base * max(1.0, cost_multiplier), 5)

    def _get_default_recompute_cost(self, task_type: str) -> float:
        """Get default recompute cost for task type."""
        # In production, this would vary by task complexity
        return 0.021


def create_decision_input(
    task_type: TaskType | str,
    candidate: MatchCandidate,
    fragment: SkillFragment | None,
    allow_adaptation: bool = True,
    allow_recompute: bool = True,
    adaptation_cost: float | None = None,
    recompute_cost: float | None = None,
) -> DecisionInput:
    """Factory function to create DecisionInput from candidate."""
    return DecisionInput(
        task_type=task_type,
        distance=1.0 - candidate.score,  # Convert similarity to distance
        similarity_score=candidate.score,
        fragment=fragment,
        allow_adaptation=allow_adaptation,
        allow_recompute=allow_recompute,
        adaptation_cost_estimate=adaptation_cost,
        recompute_cost=recompute_cost,
    )
