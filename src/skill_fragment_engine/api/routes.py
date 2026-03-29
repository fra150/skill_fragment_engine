"""FastAPI routes for SFE."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, status

import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.enums import TaskType
from skill_fragment_engine.core.models import ExecutionRequest
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.retrieval.matcher import SkillMatcherLayer
from skill_fragment_engine.validation.validator import ValidatorEngine
from skill_fragment_engine.capture.retrospector import Fragmenter
from skill_fragment_engine.governance.decay_manager import DecayManager
from skill_fragment_engine.governance.pruning_scheduler import PruningScheduler
from skill_fragment_engine.api.schemas import (
    ExecuteRequest,
    ExecutionResponse,
    FragmentResponse,
    FragmentSearchRequest,
    FragmentSearchResponse,
    MetricsResponse,
    PruningResponse,
    HealthResponse,
    ErrorResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["SFE"])

# Dependency injection
settings = get_settings()


def get_execution_engine() -> ExecutionEngine:
    """Get execution engine instance."""
    return ExecutionEngine()


def get_fragmenter() -> Fragmenter:
    """Get fragmenter instance."""
    return Fragmenter()


# =============================================================================
# Health & Info
# =============================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow(),
    )


# =============================================================================
# Execution
# =============================================================================


@router.post(
    "/execute",
    response_model=ExecutionResponse,
    responses={
        500: {"model": ErrorResponse},
    },
    tags=["Execution"],
)
async def execute_task(
    request: ExecuteRequest,
    engine: Annotated[ExecutionEngine, Depends(get_execution_engine)],
) -> ExecutionResponse:
    """
    Execute a task through SFE.

    The system will:
    1. Search for similar cached fragments
    2. Validate if a fragment can be reused
    3. Execute: reuse cached result, adapt it, or compute fresh
    4. Capture the result as a new fragment (optional)
    """
    logger.info(
        "execute_request",
        task_type=request.task_type,
        prompt_length=len(request.prompt),
    )

    try:
        # Convert to internal request model
        exec_request = ExecutionRequest(
            task_type=request.task_type,
            prompt=request.prompt,
            context=request.context,
            parameters=request.parameters,
            options=request.options,
        )

        # Execute
        response = await engine.execute(exec_request)

        # Convert to response model
        return ExecutionResponse(
            execution_id=response.execution_id,
            decision=response.decision,
            result=response.result,
            metadata={
                "execution_id": response.metadata.execution_id,
                "decision": response.metadata.decision,
                "fragment_id": response.metadata.fragment_id,
                "variant_id": response.metadata.variant_id,
                "cost": response.metadata.cost,
                "latency_ms": response.metadata.latency_ms,
                "cost_saved": response.metadata.cost_saved,
                "decision_reason": response.metadata.decision_reason,
            },
        )

    except Exception as e:
        logger.error("execute_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# =============================================================================
# Fragment Management
# =============================================================================


@router.get(
    "/fragment/{fragment_id}",
    response_model=FragmentResponse,
    responses={
        404: {"model": ErrorResponse},
    },
    tags=["Fragments"],
)
async def get_fragment(
    fragment_id: UUID,
) -> FragmentResponse:
    """
    Get a fragment by ID.

    Returns fragment details including patterns and metrics.
    """
    # In production, this would fetch from storage
    # For now, return placeholder
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Fragment {fragment_id} not found",
    )


@router.get(
    "/fragment/search",
    response_model=list[FragmentSearchResponse],
    tags=["Fragments"],
)
async def search_fragments(
    request: Annotated[FragmentSearchRequest, Depends()],
) -> list[FragmentSearchResponse]:
    """
    Search fragments by semantic similarity.

    Returns fragments ranked by similarity to the query.
    """
    matcher = SkillMatcherLayer()

    candidates = await matcher.find_candidates(
        prompt=request.query,
        task_type=request.task_type,
        top_k=request.top_k,
    )

    return [
        FragmentSearchResponse(
            fragment_id=candidate.fragment_id,
            score=candidate.score,
            task_type=request.task_type or "unknown",
        )
        for candidate in candidates
        if candidate.score >= request.min_score
    ]


@router.post(
    "/fragment",
    response_model=FragmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Fragments"],
)
async def create_fragment(
    request: ExecuteRequest,
    fragmenter: Annotated[Fragmenter, Depends(get_fragmenter)],
) -> FragmentResponse:
    """
    Create a fragment manually.

    Useful for pre-populating the cache with known good results.
    """
    # In production, this would validate and store
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Manual fragment creation not yet implemented",
    )


@router.post(
    "/fragment/{fragment_id}/validate",
    response_model=dict,
    tags=["Fragments"],
)
async def validate_fragment(
    fragment_id: UUID,
    prompt: str,
    context: dict | None = None,
    parameters: dict | None = None,
) -> dict:
    """
    Trigger re-validation of a fragment.

    Checks if the fragment is still valid for the given input.
    """
    # In production, this would trigger validation
    return {
        "fragment_id": str(fragment_id),
        "valid": True,
        "reason": "Fragment validated successfully",
    }


# =============================================================================
# Metrics
# =============================================================================


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    tags=["Metrics"],
)
async def get_metrics() -> MetricsResponse:
    """
    Get system-wide metrics.

    Returns current performance statistics.
    """
    # In production, this would aggregate from storage
    return MetricsResponse(
        total_fragments=0,
        active_fragments=0,
        reuse_rate=0.0,
        avg_cost_per_request=0.0,
        total_cost_saved=0.0,
        latency_p50_ms=0.0,
        latency_p99_ms=0.0,
    )


# =============================================================================
# Admin
# =============================================================================


@router.post(
    "/admin/prune",
    response_model=PruningResponse,
    tags=["Admin"],
)
async def trigger_pruning() -> PruningResponse:
    """
    Trigger manual pruning cycle.

    Removes obsolete, duplicate, and low-quality fragments.
    """
    logger.info("manual_pruning_triggered")

    # In production, this would run pruning on actual storage
    return PruningResponse(
        success=True,
        total_removed=0,
        decay_removals=0,
        duplicate_removals=0,
        stale_removals=0,
        low_quality_removals=0,
        failure_removals=0,
    )


@router.post(
    "/admin/decay",
    response_model=dict,
    tags=["Admin"],
)
async def trigger_decay() -> dict:
    """
    Trigger manual decay recalculation.

    Updates decay scores for all fragments.
    """
    logger.info("manual_decay_triggered")

    return {
        "success": True,
        "fragments_updated": 0,
        "fragments_deactivated": 0,
    }
