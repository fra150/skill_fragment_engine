"""Adapt executor - modifies cached output for new input."""

from __future__ import annotations

import structlog
from uuid import uuid4

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.models import (
    SkillFragment,
    ExecutionRequest,
    Variant,
    FragmentPattern,
)

logger = structlog.get_logger(__name__)


class AdaptExecutor:
    """
    Executes ADAPT decision.

    Takes a cached fragment and adapts it to the new input context.
    This is the complex case - it may involve:
    - Parameter injection
    - Style modification
    - Structure adjustment
    """

    def __init__(self):
        self.settings = get_settings()

    async def execute(
        self,
        fragment: SkillFragment | None,
        request: ExecutionRequest,
    ) -> tuple[any, str | None]:
        """
        Execute adaptation.

        Args:
            fragment: Fragment to adapt
            request: New input request

        Returns:
            Tuple of (adapted_result, variant_id)
        """
        if fragment is None:
            raise ValueError("Cannot adapt: fragment is None")

        logger.info(
            "adapt_execution",
            fragment_id=fragment.fragment_id,
            task_type=request.task_type,
        )

        # Get the cached output as base
        base_output = fragment.output_schema.result

        # Adapt based on task type
        adapted_output = await self._adapt_output(
            base_output=base_output,
            fragment=fragment,
            request=request,
        )

        # Create variant record
        variant = self._create_variant(
            parent=fragment,
            original_output=base_output,
            adapted_output=adapted_output,
            request=request,
        )

        # Update fragment metrics
        fragment.metrics.adapt_count += 1
        fragment.metrics.total_cost_saved += (
            self.settings.base_execution_cost - self.settings.adaptation_cost
        )

        logger.info(
            "adapt_complete",
            fragment_id=fragment.fragment_id,
            variant_id=variant.variant_id,
        )

        return adapted_output, str(variant.variant_id)

    async def _adapt_output(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt the base output to the new input.

        Strategy depends on task type:
        - code_generation: Inject new parameters into generated code
        - text_summarization: Adjust summary length/style
        - translation: Modify tense/style
        - etc.
        """
        task_type = request.task_type

        if task_type == "code_generation":
            return await self._adapt_code(base_output, fragment, request)
        elif task_type == "text_summarization":
            return await self._adapt_summary(base_output, fragment, request)
        elif task_type == "translation":
            return await self._adapt_translation(base_output, fragment, request)
        else:
            # Generic adaptation - return base with minor modifications
            return self._generic_adapt(base_output, request)

    async def _adapt_code(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt generated code.

        Common adaptations:
        - Change language (Python -> JavaScript)
        - Change style (functional -> OOP)
        - Add/remove parameters
        """
        # Extract patterns from fragment
        patterns = fragment.output_schema.fragment_patterns

        # Simple strategy: if output is a string (code), try to modify
        if isinstance(base_output, str):
            # In real impl, this would use LLM for complex adaptations
            # For now, just return as-is with parameter injection
            modified = base_output

            # Inject parameters from request into code
            for key, value in request.parameters.items():
                if isinstance(value, str):
                    # Simple string replacement
                    modified = modified.replace(f"{{{key}}}", value)

            return modified

        return base_output

    async def _adapt_summary(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt a summary.

        Common adaptations:
        - Change length (shorter/longer)
        - Change tone (formal/casual)
        - Change focus (technical/business)
        """
        if isinstance(base_output, str):
            # Simple adaptation based on request parameters
            target_length = request.parameters.get("length", "medium")

            if target_length == "short":
                # Truncate to first 2 sentences
                sentences = base_output.split(". ")
                return ". ".join(sentences[:2]) + "."
            elif target_length == "long":
                # Expand with more detail (placeholder)
                return base_output

        return base_output

    async def _adapt_translation(
        self,
        base_output: any,
        fragment: SkillFragment,
        request: ExecutionRequest,
    ) -> any:
        """
        Adapt a translation.

        Common adaptations:
        - Change formality level
        - Adjust tone
        - Fix terminology
        """
        # Similar to summary adaptation
        return base_output

    def _generic_adapt(self, base_output: any, request: ExecutionRequest) -> any:
        """Generic adaptation fallback."""
        # Just merge request parameters into output if possible
        if isinstance(base_output, dict):
            return {**base_output, **request.parameters}
        return base_output

    def _create_variant(
        self,
        parent: SkillFragment,
        original_output: any,
        adapted_output: any,
        request: ExecutionRequest,
    ) -> Variant:
        """Create a variant record for the adaptation."""
        variant = Variant(
            variant_id=uuid4(),
            parent_fragment_id=parent.fragment_id,
            created_from="adaptation",
            diff_type="output_modification",
            before_snapshot={"result": original_output},
            after_snapshot={"result": adapted_output},
            reason=f"Adapted for new context",
            performance_delta={
                "quality_delta": 0.0,  # Would be computed from validation
            },
        )

        # Link to parent
        parent.variants.append(variant.variant_id)

        return variant

    def estimate_cost(self) -> float:
        """Estimate cost for adaptation."""
        return self.settings.adaptation_cost
