"""Process Retrospector - captures execution as a fragment."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import structlog

from skill_fragment_engine.capture.extractors import get_extractor_for_task_type
from skill_fragment_engine.core.enums import TaskType, ValidationOutcome
from skill_fragment_engine.core.models import (
    ExecutionRequest,
    ExecutionResponse,
    InputSignature,
    OutputSchema,
    FragmentMetrics,
    FragmentPattern,
    SkillFragment,
    ValidationRecord,
)

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionData:
    """Container for execution data to capture."""

    request: ExecutionRequest
    response: ExecutionResponse
    cost: float
    latency: float
    success: bool = True
    error: str | None = None


class ProcessRetrospector:
    """
    Captures the complete execution process as a SkillFragment.

    This is the "ritrospettiva" component - it doesn't just capture
    the output, but documents HOW the result was achieved.
    """

    def __init__(self):
        self._pattern_extractors = {}

    async def capture(self, execution: ExecutionData) -> SkillFragment | None:
        """
        Capture execution as a new fragment.

        Args:
            execution: Execution data to capture

        Returns:
            New SkillFragment, or None if capture should be skipped
        """
        if not execution.request.capture_fragment:
            logger.debug("capture_skipped", reason="capture_fragment_disabled")
            return None

        if not execution.success:
            logger.debug("capture_skipped", reason="execution_failed")
            return None

        logger.info(
            "capture_started",
            task_type=execution.request.task_type,
        )

        try:
            # 1. Create input signature
            input_signature = self._create_input_signature(execution.request)

            # 2. Extract patterns from output
            patterns = await self._extract_patterns(
                output=execution.response.result,
                task_type=execution.request.task_type,
            )

            # 3. Document process steps
            steps = self._document_steps(execution)

            # 4. Build output schema
            output_schema = OutputSchema(
                result=execution.response.result,
                fragment_patterns=patterns,
                process_steps=steps,
                output_hash=self._hash_output(execution.response.result),
            )

            # 5. Create fragment
            fragment = SkillFragment(
                fragment_id=uuid4(),
                task_type=execution.request.task_type,
                input_signature=input_signature,
                output_schema=output_schema,
                metrics=FragmentMetrics(
                    creation_cost=execution.cost,
                    creation_latency=execution.latency,
                ),
                decay_score=1.0,  # Fresh fragment
                quality_score=self._estimate_quality(execution),
                is_active=True,
            )

            logger.info(
                "capture_complete",
                fragment_id=fragment.fragment_id,
                patterns_extracted=len(patterns),
            )

            return fragment

        except Exception as e:
            logger.error(
                "capture_failed",
                task_type=execution.request.task_type,
                error=str(e),
            )
            return None

    def _create_input_signature(self, request: ExecutionRequest) -> InputSignature:
        """Create hash-based input signature."""
        return InputSignature.create(
            prompt=request.prompt,
            context=request.context,
            parameters=request.parameters,
        )

    async def _extract_patterns(
        self,
        output: Any,
        task_type: str,
    ) -> list[FragmentPattern]:
        """Extract reusable patterns from output."""
        extractor = get_extractor_for_task_type(task_type)

        try:
            patterns = await extractor.extract(output, task_type)
            return patterns
        except Exception as e:
            logger.warning(
                "pattern_extraction_failed",
                task_type=task_type,
                error=str(e),
            )
            return []

    def _document_steps(self, execution: ExecutionData) -> list[str]:
        """Document the process steps taken."""
        steps = [
            "receive_request",
            "create_input_signature",
        ]

        # Add steps based on decision
        decision = execution.response.metadata.decision.value
        if decision == "reuse":
            steps.extend([
                "retrieve_cached_fragment",
                "validate_context",
                "return_cached_result",
            ])
        elif decision == "adapt":
            steps.extend([
                "retrieve_cached_fragment",
                "validate_context",
                "adapt_output",
                "create_variant",
            ])
        elif decision == "recompute":
            steps.extend([
                "retrieve_candidates",
                "validate_candidates",
                "call_llm",
                "process_result",
            ])

        steps.append("capture_fragment")
        return steps

    def _hash_output(self, output: Any) -> str:
        """Create hash of output for deduplication."""
        normalized = json.dumps(output, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _estimate_quality(self, execution: ExecutionData) -> float:
        """
        Estimate quality of the execution result.

        In production, this would use:
        - User feedback
        - Automated validation
        - Success metrics
        """
        base_quality = 0.7  # Base quality score

        # Adjust based on execution success
        if not execution.success:
            base_quality -= 0.3

        # Adjust based on cost (expensive = probably complex)
        if execution.cost > 0.01:
            base_quality += 0.1

        # Adjust based on latency (faster = better)
        if execution.latency < 1.0:
            base_quality += 0.1

        return max(0.0, min(1.0, base_quality))


class Fragmenter:
    """
    High-level fragment management.

    Handles creation, storage, and lifecycle of fragments.
    """

    def __init__(self, retrospector: ProcessRetrospector | None = None):
        self.retrospector = retrospector or ProcessRetrospector()

    async def create_fragment(
        self,
        request: ExecutionRequest,
        response: ExecutionResponse,
        cost: float,
        latency: float,
    ) -> SkillFragment | None:
        """Create and store a new fragment."""
        execution_data = ExecutionData(
            request=request,
            response=response,
            cost=cost,
            latency=latency,
            success=response.metadata.decision.value != "recompute"
            or response.result is not None,
        )

        return await self.retrospector.capture(execution_data)

    async def update_fragment(
        self,
        fragment: SkillFragment,
        validation_record: ValidationRecord,
    ) -> SkillFragment:
        """Update fragment with new validation record."""
        fragment.add_validation(validation_record)
        return fragment
