"""Main execution engine for SFE."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.enums import Decision
from skill_fragment_engine.core.models import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionMetadata,
    SkillFragment,
    MatchCandidate,
    FragmentMetrics,
    InputSignature,
    OutputSchema,
)
from skill_fragment_engine.core.metrics import metrics_collector
from skill_fragment_engine.execution.reuse_executor import ReuseExecutor
from skill_fragment_engine.execution.adapt_executor import AdaptExecutor
from skill_fragment_engine.execution.recompute_executor import RecomputeExecutor
from skill_fragment_engine.retrieval.matcher import SkillMatcherLayer
from skill_fragment_engine.validation.validator import ValidatorEngine, ValidationResult
from skill_fragment_engine.store import FragmentStore

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionContext:
    """Context maintained throughout execution pipeline."""

    execution_id: UUID
    request: ExecutionRequest
    start_time: float = field(default_factory=time.time)

    # Pipeline state
    candidates: list[MatchCandidate] = field(default_factory=list)
    fragments: dict[str, SkillFragment] = field(default_factory=dict)
    validation_result: ValidationResult | None = None

    # Execution result
    result: Any = None
    decision: Decision = Decision.RECOMPUTE
    fragment: SkillFragment | None = None
    variant_id: UUID | None = None
    cost: float = 0.0
    cost_saved: float = 0.0
    tokens_used: int = 0
    error: str | None = None

    @property
    def latency_ms(self) -> float:
        """Compute latency in milliseconds."""
        return (time.time() - self.start_time) * 1000

    @property
    def success(self) -> bool:
        """Check if execution succeeded."""
        return self.error is None and self.result is not None


class ExecutionEngine:
    """
    Main execution engine for Skill Fragment Engine.

    Orchestrates the full pipeline:
    1. Retrieval - find candidate fragments
    2. Validation - decide if fragment is reusable
    3. Execution - reuse, adapt, or recompute
    4. Capture - store result as new fragment (if applicable)
    """

    def __init__(
        self,
        matcher: SkillMatcherLayer | None = None,
        validator: ValidatorEngine | None = None,
        store: FragmentStore | None = None,
        reuse_executor: ReuseExecutor | None = None,
        adapt_executor: AdaptExecutor | None = None,
        recompute_executor: RecomputeExecutor | None = None,
    ):
        self.store = store or FragmentStore()
        self.matcher = matcher or SkillMatcherLayer(store=self.store)
        self.validator = validator or ValidatorEngine()

        # Executors
        self.reuse_executor = reuse_executor or ReuseExecutor()
        self.adapt_executor = adapt_executor or AdaptExecutor()
        self.recompute_executor = recompute_executor or RecomputeExecutor()

        self.settings = get_settings()

    async def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """
        Execute a task through the SFE pipeline.

        Args:
            request: Execution request

        Returns:
            Execution response with result and metadata
        """
        context = ExecutionContext(
            execution_id=uuid4(),
            request=request,
        )
        
        # Start latency timer
        metrics_collector.start_timer("total_latency")

        try:
            logger.info(
                "execution_started",
                execution_id=context.execution_id,
                task_type=request.task_type,
            )

            # Step 1: Retrieval - find candidates
            await self._retrieve_candidates(context)

            # Step 2: Validation - decide action
            await self._validate(context)

            # Step 3: Execution - perform action
            await self._execute_decision(context)

            logger.info(
                "execution_completed",
                execution_id=context.execution_id,
                decision=context.decision.value,
                latency_ms=context.latency_ms,
                cost=context.cost,
            )
            
            # Record metrics
            total_latency = metrics_collector.stop_timer("total_latency")
            metrics_collector.record_request(
                decision=context.decision.value,
                latency_ms=context.latency_ms,
            )

        except Exception as e:
            logger.error(
                "execution_failed",
                execution_id=context.execution_id,
                error=str(e),
            )
            context.error = str(e)
            context.decision = Decision.RECOMPUTE

        # Build response
        return self._build_response(context)

    async def _retrieve_candidates(self, context: ExecutionContext) -> None:
        """Retrieve candidate fragments for the request."""
        metrics_collector.start_timer("retrieval_latency")
        candidates = await self.matcher.find_candidates(
            prompt=context.request.prompt,
            context=context.request.context,
            parameters=context.request.parameters,
            task_type=context.request.task_type,
        )

        context.candidates = candidates
        
        # Record retrieval latency
        retrieval_latency = metrics_collector.stop_timer("retrieval_latency")
        metrics_collector.retrieval_latency.observe(retrieval_latency)

        logger.debug(
            "candidates_retrieved",
            count=len(candidates),
        )

    async def _validate(self, context: ExecutionContext) -> None:
        """Validate candidates and decide action."""
        metrics_collector.start_timer("validation_latency")
        
        # Load fragments for candidates
        fragments: dict[str, SkillFragment] = {}
        for candidate in context.candidates:
            fragment = self.store.get_fragment(candidate.fragment_id)
            if fragment is not None:
                fragments[candidate.fragment_id] = fragment
        context.fragments = fragments

        # Validate
        validation_result = await self.validator.validate(
            request=context.request,
            candidates=context.candidates,
            fragments=context.fragments,
        )

        context.validation_result = validation_result
        context.decision = validation_result.decision
        context.fragment = validation_result.fragment
        
        # Record validation latency
        validation_latency = metrics_collector.stop_timer("validation_latency")
        metrics_collector.validation_latency.observe(validation_latency)

    async def _execute_decision(self, context: ExecutionContext) -> None:
        """Execute the validated decision."""
        metrics_collector.start_timer("execution_latency")
        
        request = context.request
        validation = context.validation_result

        if validation is None:
            # No validation = default to recompute
            context.decision = Decision.RECOMPUTE

        if context.decision == Decision.REUSE:
            context.result = await self.reuse_executor.execute(
                fragment=context.fragment,
                request=request,
            )
            context.cost = self.settings.reuse_cost
            context.cost_saved = self.settings.base_execution_cost - context.cost

            # Update validation record
            if validation and validation.validation_record:
                validation.validation_record.cost_saved = context.cost_saved
                validation.validation_record.latency_saved = (
                    self.settings.base_execution_cost - context.latency_ms / 1000
                )

        elif context.decision == Decision.ADAPT:
            context.result, variant_id_str = await self.adapt_executor.execute(
                fragment=context.fragment,
                request=request,
            )
            context.variant_id = UUID(variant_id_str) if variant_id_str else None
            context.cost = self.settings.adaptation_cost
            context.cost_saved = self.settings.base_execution_cost - context.cost

        elif context.decision == Decision.RECOMPUTE:
            self._inject_cognitive_history(context)
            context.result = await self.recompute_executor.execute(
                request=request,
            )
            context.cost = self.settings.base_execution_cost
            context.cost_saved = 0.0
            if isinstance(context.result, dict) and "usage" in context.result:
                usage = context.result["usage"] or {}
                context.tokens_used = usage.get("total_tokens", 0)
            
        # Record execution latency
        execution_latency = metrics_collector.stop_timer("execution_latency")
        metrics_collector.execution_latency.observe(execution_latency)

        await self._persist_after_execution(context)

    def _inject_cognitive_history(self, context: ExecutionContext) -> None:
        if not context.candidates:
            return
        blocks: list[str] = []
        for candidate in context.candidates[:3]:
            if candidate.match_type == "exact":
                continue
            fragment = context.fragments.get(candidate.fragment_id)
            if fragment is None:
                continue
            prompt = self.store.get_prompt(candidate.fragment_id) or ""
            output_preview = str(fragment.output_schema.result)
            blocks.append(
                "\n".join(
                    [
                        "=== FRAGMENT FROM PREVIOUS EXECUTION ===",
                        f"TASK TYPE: {fragment.task_type}",
                        f"ORIGINAL INPUT: {prompt[:200]}",
                        f"PROCESS STEPS: {', '.join(fragment.output_schema.process_steps)}",
                        f"OUTPUT PREVIEW: {output_preview[:500]}",
                        f"DECAY SCORE: {fragment.decay_score:.2f}",
                        f"QUALITY SCORE: {fragment.quality_score:.2f}",
                        "=== END FRAGMENT ===",
                    ]
                )
            )

        if not blocks:
            return

        history = (
            f"COGNITIVE HISTORY — {len(blocks)} relevant past execution(s) found.\n"
            "Read these before starting. Use them to avoid repeating work.\n\n"
            + "\n\n".join(blocks)
        )
        if "_sfe_cognitive_history" not in context.request.context:
            context.request.context["_sfe_cognitive_history"] = history

    async def _persist_after_execution(self, context: ExecutionContext) -> None:
        if context.decision in (Decision.REUSE, Decision.ADAPT) and context.fragment is not None:
            self.store.update_fragment(context.fragment)
            return

        if not context.request.capture_fragment:
            return
        if not context.success:
            return

        input_signature = InputSignature.create(
            prompt=context.request.prompt,
            context=context.request.context,
            parameters=context.request.parameters,
        )
        output_schema = OutputSchema(
            result=context.result,
            process_steps=[
                "receive_request",
                "retrieve_candidates",
                "validate_candidates",
                "call_llm",
                "capture_fragment",
            ],
        )
        fragment = SkillFragment(
            task_type=context.request.task_type,
            input_signature=input_signature,
            output_schema=output_schema,
            metrics=FragmentMetrics(
                creation_cost=context.cost,
                creation_latency=context.latency_ms / 1000,
            ),
            decay_score=1.0,
            quality_score=0.7,
            is_active=True,
        )
        self.store.save_fragment(
            fragment=fragment,
            prompt=context.request.prompt,
            context=context.request.context,
            parameters=context.request.parameters,
        )
        embedding = await self.matcher.compute_embedding(
            prompt=context.request.prompt,
            context=context.request.context,
        )
        self.matcher.vector_store.add(str(fragment.fragment_id), embedding)
        self.matcher.vector_store.save()
        context.fragment = fragment

    def _build_response(self, context: ExecutionContext) -> ExecutionResponse:
        """Build execution response from context."""
        metadata = ExecutionMetadata(
            execution_id=context.execution_id,
            decision=context.decision,
            fragment_id=context.fragment.fragment_id if context.fragment else None,
            variant_id=context.variant_id,
            cost=context.cost,
            latency_ms=context.latency_ms,
            cost_saved=context.cost_saved,
            decision_reason=(
                context.validation_result.reason
                if context.validation_result
                else "default"
            ),
            tokens_used=context.tokens_used,
        )

        return ExecutionResponse(
            execution_id=context.execution_id,
            decision=context.decision,
            result=context.result,
            metadata=metadata,
        )

    async def execute_batch(
        self,
        requests: list[ExecutionRequest],
    ) -> list[ExecutionResponse]:
        """
        Execute multiple requests in parallel.

        For production, this should use asyncio.gather with rate limiting.
        """
        import asyncio

        tasks = [self.execute(req) for req in requests]
        return await asyncio.gather(*tasks)
