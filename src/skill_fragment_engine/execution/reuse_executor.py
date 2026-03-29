"""Reuse executor - returns cached fragment output."""

from __future__ import annotations

import structlog

from skill_fragment_engine.core.models import SkillFragment, ExecutionRequest

logger = structlog.get_logger(__name__)


class ReuseExecutor:
    """
    Executes REUSE decision.

    Simply returns the cached output from the fragment.
    Minimal processing, maximum speed.
    """

    async def execute(
        self,
        fragment: SkillFragment | None,
        request: ExecutionRequest,
    ) -> any:
        """
        Execute reuse by returning cached result.

        Args:
            fragment: Fragment with cached result
            request: Original request (for logging)

        Returns:
            Cached output from fragment
        """
        if fragment is None:
            logger.error("reuse_executor_no_fragment")
            raise ValueError("Cannot reuse: fragment is None")

        logger.info(
            "reuse_execution",
            fragment_id=fragment.fragment_id,
            task_type=request.task_type,
            reuse_count=fragment.metrics.reuse_count + 1,
        )

        # Update fragment metrics (in real impl, this would be async DB update)
        fragment.metrics.reuse_count += 1

        # Return cached result
        return fragment.output_schema.result

    def estimate_cost(self) -> float:
        """Estimate cost for reuse."""
        from skill_fragment_engine.core.config import get_settings
        return get_settings().reuse_cost
