"""Validator Engine - decides when to reuse/adapt/recompute."""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from skill_fragment_engine.core.config import get_settings, get_task_thresholds
from skill_fragment_engine.core.enums import Decision, TaskType, ValidationOutcome
from skill_fragment_engine.core.models import (
    ExecutionRequest,
    SkillFragment,
    MatchCandidate,
    ValidationRecord,
)
from skill_fragment_engine.validation.context_comparator import ContextComparator, compute_embedding_distance
from skill_fragment_engine.validation.decision_classifier import (
    DecisionClassifier,
    DecisionInput,
    DecisionOutput,
)

logger = structlog.get_logger(__name__)


@dataclass
class ValidationResult:
    """Result from validation process."""

    decision: Decision
    fragment: SkillFragment | None
    candidate: MatchCandidate | None
    context_distance: float
    score: float
    reason: str
    validation_record: ValidationRecord | None = None


class ValidatorEngine:
    """
    Validates whether a fragment can be reused for a given input.

    This is the core decision engine of SFE. It:
    1. Compares input context with fragment context
    2. Applies task-type specific thresholds
    3. Decides between REUSE, ADAPT, or RECOMPUTE
    """

    def __init__(
        self,
        context_comparator: ContextComparator | None = None,
        decision_classifier: DecisionClassifier | None = None,
    ):
        self.context_comparator = context_comparator or ContextComparator()
        self.decision_classifier = decision_classifier or DecisionClassifier()
        self.settings = get_settings()

    async def validate(
        self,
        request: ExecutionRequest,
        candidates: list[MatchCandidate],
        fragments: dict[str, SkillFragment],
    ) -> ValidationResult:
        """
        Validate the best candidate for the given request.

        Args:
            request: Original execution request
            candidates: List of candidate fragments from retrieval
            fragments: Map of fragment_id -> SkillFragment

        Returns:
            Validation result with decision and reasoning
        """
        if not candidates:
            logger.info("no_candidates", task_type=request.task_type)
            return self._create_recompute_result(
                reason="No matching candidates found"
            )

        # Find best candidate
        best_candidate = candidates[0]
        best_fragment = fragments.get(best_candidate.fragment_id)

        if best_fragment is None:
            logger.warning(
                "fragment_not_found",
                fragment_id=best_candidate.fragment_id
            )
            return self._create_recompute_result(
                reason=f"Fragment {best_candidate.fragment_id} not found"
            )

        if best_candidate.match_type == "exact":
            validation_record = ValidationRecord(
                fragment_id=best_fragment.fragment_id,
                timestamp=datetime.utcnow(),
                validation_type="exact_match",
                context_distance=0.0,
                outcome=ValidationOutcome.REUSED_SUCCESSFULLY,
            )
            return ValidationResult(
                decision=Decision.REUSE,
                fragment=best_fragment,
                candidate=best_candidate,
                context_distance=0.0,
                score=0.99,
                reason="Exact match on stored input signature",
                validation_record=validation_record,
            )

        # Compute context distance
        context_distance = await self._compute_context_distance(
            request=request,
            fragment=best_fragment,
        )

        logger.debug(
            "candidate_eval",
            fragment_id=best_fragment.fragment_id,
            similarity_score=best_candidate.score,
            context_distance=context_distance,
        )

        # Classify decision
        decision_output = self.decision_classifier.classify(
            DecisionInput(
                task_type=request.task_type,
                distance=context_distance,
                similarity_score=best_candidate.score,
                fragment=best_fragment,
                allow_adaptation=request.allow_adaptation,
                allow_recompute=request.allow_recompute,
                recompute_cost=self.settings.base_execution_cost,
            )
        )

        # Create validation record
        validation_record = ValidationRecord(
            fragment_id=best_fragment.fragment_id,
            timestamp=datetime.utcnow(),
            validation_type="context_comparison",
            context_distance=context_distance,
            outcome=self._map_decision_to_outcome(decision_output.decision),
        )

        result = ValidationResult(
            decision=decision_output.decision,
            fragment=best_fragment,
            candidate=best_candidate,
            context_distance=context_distance,
            score=decision_output.score,
            reason=decision_output.reason,
            validation_record=validation_record,
        )

        logger.info(
            "validation_complete",
            decision=result.decision.value,
            fragment_id=best_fragment.fragment_id,
            reason=result.reason,
        )

        return result

    async def _compute_context_distance(
        self,
        request: ExecutionRequest,
        fragment: SkillFragment,
    ) -> float:
        """
        Compute distance between request input and fragment input.

        Uses embedding distance for prompts and structural comparison
        for context/parameters.
        """
        request_input = {
            "prompt": request.prompt,
            "context": request.context,
            "parameters": request.parameters,
        }

        fragment_input = {
            "prompt": "placeholder",  # Will use embedding distance instead
            "context": self._extract_context_from_signature(fragment.input_signature),
            "parameters": fragment.input_signature.parameters,
        }

        # Get embedding for prompts
        from skill_fragment_engine.retrieval.embedder import EmbeddingService

        embedder = EmbeddingService()
        request_embedding = await embedder.embed_context(
            request.prompt,
            request.context,
        )

        # Get fragment embedding from storage
        fragment_embedding = await self._get_fragment_embedding(fragment)

        if fragment_embedding:
            embedding_distance = compute_embedding_distance(
                request_embedding,
                fragment_embedding,
            )
        else:
            # Fallback to text comparison
            embedding_distance = 0.5

        # Structural distance (context + parameters)
        structural_distance = self.context_comparator.compute_distance(
            request_input,
            fragment_input,
        )

        # Weighted combination (embedding has more weight)
        total_distance = 0.6 * embedding_distance + 0.4 * structural_distance

        return round(total_distance, 4)

    def _extract_context_from_signature(self, signature) -> dict[str, Any]:
        """Extract context dict from input signature."""
        # In actual implementation, this would be stored differently
        # For now, return empty dict as context is not directly stored
        return {}

    async def _get_fragment_embedding(
        self,
        fragment: SkillFragment,
    ) -> list[float] | None:
        """Get embedding for a fragment."""
        from skill_fragment_engine.retrieval.vector_store import VectorStore

        try:
            vector_store = VectorStore()
            return vector_store.get(str(fragment.fragment_id))
        except Exception:
            return None

    def _map_decision_to_outcome(self, decision: Decision) -> ValidationOutcome:
        """Map decision to validation outcome."""
        mapping = {
            Decision.REUSE: ValidationOutcome.REUSED_SUCCESSFULLY,
            Decision.ADAPT: ValidationOutcome.ADAPTED,
            Decision.RECOMPUTE: ValidationOutcome.RECOMPUTED,
        }
        return mapping.get(decision, ValidationOutcome.RECOMPUTED)

    def _create_recompute_result(self, reason: str) -> ValidationResult:
        """Create a default recompute result."""
        return ValidationResult(
            decision=Decision.RECOMPUTE,
            fragment=None,
            candidate=None,
            context_distance=1.0,
            score=1.0,
            reason=reason,
        )

    def get_thresholds(self, task_type: TaskType | str) -> Any:
        """Get thresholds for a task type."""
        task_type_str = (
            task_type.value if isinstance(task_type, TaskType) else task_type
        )
        return get_task_thresholds(task_type_str)
