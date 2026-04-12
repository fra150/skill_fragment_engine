"""FastAPI routes for SFE."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, status

import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.enums import TaskType, FeedbackType, FeedbackCategory
from skill_fragment_engine.core.models import ExecutionRequest, UserFeedback
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.retrieval.matcher import SkillMatcherLayer
from skill_fragment_engine.validation.validator import ValidatorEngine
from skill_fragment_engine.capture.retrospector import Fragmenter
from skill_fragment_engine.governance.decay_manager import DecayManager
from skill_fragment_engine.governance.pruning_scheduler import PruningScheduler
from skill_fragment_engine.services.feedback_service import get_feedback_service
from skill_fragment_engine.api.schemas import (
    ExecuteRequest,
    ExecutionResponse,
    ExecutionMetadataResponse,
    FragmentResponse,
    FragmentSearchRequest,
    FragmentSearchResponse,
    MetricsResponse,
    PruningResponse,
    HealthResponse,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackStatsResponse,
)
from skill_fragment_engine.core.metrics import metrics_collector

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


def get_feedback_svc():
    """Get feedback service instance."""
    return get_feedback_service()


# Health & Info

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

# Execution

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
        fragment_id = response.metadata.fragment_id
        variant_id = response.metadata.variant_id
        
        # Convert string IDs to UUID objects if they exist
        if fragment_id and isinstance(fragment_id, str):
            try:
                fragment_id = UUID(fragment_id)
            except ValueError:
                fragment_id = None
        if variant_id and isinstance(variant_id, str):
            try:
                variant_id = UUID(variant_id)
            except ValueError:
                variant_id = None
            
        return ExecutionResponse(
            execution_id=response.execution_id,
            decision=response.decision,
            result=response.result,
            metadata=ExecutionMetadataResponse(
                execution_id=response.metadata.execution_id,
                decision=response.metadata.decision,
                fragment_id=fragment_id,
                variant_id=variant_id,
                cost=response.metadata.cost,
                latency_ms=response.metadata.latency_ms,
                cost_saved=response.metadata.cost_saved,
                decision_reason=response.metadata.decision_reason,
            ),
        )

    except Exception as e:
        logger.error("execute_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )



# Fragment Management

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
            fragment_id=UUID(candidate.fragment_id),
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


# Metrics

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
    # Get metrics from collector
    metrics = metrics_collector.get_metrics()
    
    # Calculate average cost per request (simplified)
    total_requests = metrics["total_requests"]
    if total_requests > 0:
        # This is a simplified calculation - in reality we'd track actual costs
        reuse_count = metrics["reuse_count"]
        adapt_count = metrics["adapt_count"] 
        recompute_count = metrics["recompute_count"]
        
        # Approximate costs: reuse=0.000002, adapt=0.0021, recompute=0.021
        total_cost = (reuse_count * 0.000002) + (adapt_count * 0.0021) + (recompute_count * 0.021)
        avg_cost = total_cost / total_requests
    else:
        avg_cost = 0.0
    
    return MetricsResponse(
        total_fragments=metrics["active_fragments"],  # Using active as total for now
        active_fragments=metrics["active_fragments"],
        reuse_rate=metrics["reuse_rate"],
        avg_cost_per_request=avg_cost,
        total_cost_saved=metrics["total_cost_saved"],  # We'll need to implement this
        latency_p50_ms=metrics["latency_p50_ms"],
        latency_p99_ms=metrics["latency_p99_ms"],
    )

# Admin

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


# Feedback

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    tags=["Feedback"],
)
async def submit_feedback(
    request: FeedbackRequest,
    feedback_svc = Depends(get_feedback_svc),
) -> FeedbackResponse:
    """
    Submit feedback on a fragment execution.
    
    Users can provide positive, negative, or neutral feedback on fragments
    that were used in their executions. This feedback is used to:
    - Calculate fragment quality scores
    - Adjust decision thresholds automatically
    - Improve retrieval relevance
    
    Body Parameters:
    - feedback_type: positive, negative, or neutral
    - score: Quality score from 0 to 1
    - fragment_id: (optional) Related fragment ID
    - execution_id: (optional) Related execution ID
    - category: (optional) Category like quality, accuracy, relevance
    - comment: (optional) User comment
    """
    from uuid import uuid4
    
    # Create UserFeedback from request
    feedback = UserFeedback(
        feedback_id=uuid4(),
        execution_id=request.execution_id,
        fragment_id=request.fragment_id,
        variant_id=request.variant_id,
        feedback_type=request.feedback_type,
        category=request.category,
        score=request.score,
        comment=request.comment,
        expected_output=request.expected_output,
        actual_output=request.actual_output,
        user_id=request.user_id,
        session_id=request.session_id,
    )
    
    stored_feedback = await feedback_svc.add_feedback(feedback)
    
    return FeedbackResponse(
        feedback_id=stored_feedback.feedback_id,
        success=True,
        message="Feedback submitted successfully",
    )


@router.get(
    "/feedback/stats",
    response_model=FeedbackStatsResponse,
    tags=["Feedback"],
)
async def get_feedback_stats(
    fragment_id: str | None = None,
    feedback_svc = Depends(get_feedback_svc),
) -> FeedbackStatsResponse:
    """
    Get feedback statistics.
    
    Query Parameters:
    - fragment_id: (optional) Filter by specific fragment
    
    Returns aggregated feedback statistics including:
    - Total feedback count
    - Average score
    - Positive/negative/neutral breakdown
    - Category distribution
    """
    stats = await feedback_svc.get_feedback_stats(fragment_id)
    
    return FeedbackStatsResponse(**stats)


@router.get(
    "/feedback/recent",
    response_model=list[dict],
    tags=["Feedback"],
)
async def get_recent_feedback(
    limit: int = 50,
    feedback_type: str | None = None,
    feedback_svc = Depends(get_feedback_svc),
) -> list[dict]:
    """
    Get recent feedback entries.
    
    Query Parameters:
    - limit: Maximum number of feedback entries to return (default 50)
    - feedback_type: Filter by feedback type (positive/negative/neutral)
    """
    ftype = FeedbackType(feedback_type) if feedback_type else None
    feedback_list = await feedback_svc.get_recent_feedback(limit, ftype)
    
    return [
        {
            "feedback_id": str(f.feedback_id),
            "fragment_id": str(f.fragment_id) if f.fragment_id else None,
            "feedback_type": f.feedback_type.value,
            "score": f.score,
            "category": f.category.value,
            "comment": f.comment,
            "created_at": f.created_at.isoformat(),
        }
        for f in feedback_list
    ]


@router.get(
    "/fragments/{fragment_id}/quality",
    response_model=dict,
    tags=["Fragments"],
)
async def get_fragment_quality(
    fragment_id: str,
    feedback_svc = Depends(get_feedback_svc),
) -> dict:
    """
    Get quality score for a specific fragment.
    
    Returns a calculated quality score based on user feedback.
    The score is weighted by recency - recent feedback has more impact.
    """
    quality_score = await feedback_svc.get_fragment_quality_score(fragment_id)
    stats = await feedback_svc.get_feedback_stats(fragment_id)
    
    return {
        "fragment_id": fragment_id,
        "quality_score": round(quality_score, 3),
        "feedback_count": stats["total_feedback"],
        "average_score": stats["average_score"],
    }


# Versioning

@router.get(
    "/fragments/{fragment_id}/versions",
    response_model=list[dict],
    tags=["Versioning"],
)
async def get_fragment_versions(
    fragment_id: str,
    include_deprecated: bool = False,
) -> list[dict]:
    """
    Get version history for a fragment.
    
    Returns all versions of a fragment, sorted by version number (newest first).
    """
    from skill_fragment_engine.services.versioning_service import get_versioning_service
    
    versioning_svc = get_versioning_service()
    return versioning_svc.get_version_history(fragment_id, include_deprecated)


@router.post(
    "/fragments/{fragment_id}/versions",
    response_model=dict,
    tags=["Versioning"],
)
async def create_new_version(
    fragment_id: str,
    created_from: str = "improvement",
    changelog: str = "",
) -> dict:
    """
    Create a new version of a fragment.
    
    Body Parameters:
    - created_from: Reason for new version (adaptation, improvement, fix)
    - changelog: Description of changes
    """
    from skill_fragment_engine.services.versioning_service import get_versioning_service
    
    versioning_svc = get_versioning_service()
    version = versioning_svc.create_new_version(
        fragment_id=fragment_id,
        created_from=created_from,
        changelog=changelog,
    )
    
    return {
        "version_id": str(version.version_id),
        "version_number": version.version_number,
        "created_at": version.created_at.isoformat(),
        "changelog": version.changelog,
    }


@router.post(
    "/fragments/{fragment_id}/rollback/{version_number}",
    response_model=dict,
    tags=["Versioning"],
)
async def rollback_to_version(
    fragment_id: str,
    version_number: int,
    reason: str = "",
) -> dict:
    """
    Rollback to a specific version.
    
    Path Parameters:
    - fragment_id: ID of the fragment
    - version_number: Version to rollback to
    
    Query Parameters:
    - reason: Optional reason for rollback
    """
    from skill_fragment_engine.services.versioning_service import get_versioning_service
    
    versioning_svc = get_versioning_service()
    version = versioning_svc.rollback_to_version(
        fragment_id=fragment_id,
        version_number=version_number,
        reason=reason,
    )
    
    return {
        "success": True,
        "rollback_to_version": version_number,
        "new_version": version.version_number,
        "message": f"Rolled back to version {version_number}",
    }


@router.get(
    "/fragments/{fragment_id}/branches",
    response_model=list[dict],
    tags=["Versioning"],
)
async def get_fragment_branches(
    fragment_id: str,
) -> list[dict]:
    """Get all branches for a fragment."""
    from skill_fragment_engine.services.versioning_service import get_versioning_service
    
    versioning_svc = get_versioning_service()
    branches = versioning_svc.get_branches(fragment_id)
    
    return [
        {
            "branch_id": str(b.branch_id),
            "branch_name": b.branch_name,
            "base_version_id": str(b.base_version_id),
            "created_at": b.created_at.isoformat(),
            "is_default": b.is_default,
        }
        for b in branches
    ]



# Rollback

@router.get(
    "/rollback/stats",
    response_model=dict,
    tags=["Rollback"],
)
async def get_rollback_stats() -> dict:
    """Get rollback statistics."""
    from skill_fragment_engine.services.rollback_service import get_rollback_service
    
    rollback_svc = get_rollback_service()
    return rollback_svc.get_rollback_stats()


@router.get(
    "/rollback/history",
    response_model=list[dict],
    tags=["Rollback"],
)
async def get_rollback_history(
    fragment_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get rollback history."""
    from skill_fragment_engine.services.rollback_service import get_rollback_service
    
    rollback_svc = get_rollback_service()
    return rollback_svc.get_rollback_history(fragment_id, limit)


# Transfer Learning

@router.get(
    "/transfer-learning/stats",
    response_model=dict,
    tags=["Transfer Learning"],
)
async def get_transfer_learning_stats(
    task_type: str | None = None,
) -> dict:
    """Get transfer learning pattern statistics."""
    from skill_fragment_engine.services.transfer_learning_service import get_transfer_learning_service
    
    tl_svc = get_transfer_learning_service()
    return tl_svc.get_pattern_stats(task_type)


@router.get(
    "/transfer-learning/patterns",
    response_model=list[dict],
    tags=["Transfer Learning"],
)
async def get_top_patterns(
    task_type: str,
    limit: int = 10,
) -> list[dict]:
    """Get top performing adaptation patterns for a task type."""
    from skill_fragment_engine.services.transfer_learning_service import get_transfer_learning_service
    
    tl_svc = get_transfer_learning_service()
    return tl_svc.get_top_patterns(task_type, limit)


@router.post(
    "/transfer-learning/learn",
    response_model=dict,
    tags=["Transfer Learning"],
)
async def learn_from_adaptation(
    task_type: str,
    original_input: dict,
    adapted_output: Any,
    parameters: dict,
    context: dict,
    success: bool,
) -> dict:
    """Record an adaptation for transfer learning."""
    from skill_fragment_engine.services.transfer_learning_service import get_transfer_learning_service
    
    tl_svc = get_transfer_learning_service()
    tl_svc.learn_from_adaptation(
        task_type=task_type,
        original_input=original_input,
        adapted_output=adapted_output,
        parameters=parameters,
        context=context,
        success=success,
    )
    
    return {"success": True, "message": "Adaptation recorded for learning"}

@router.get(
    "/transfer-learning/suggest",
    response_model=dict,
    tags=["Transfer Learning"],
)
async def suggest_adaptation(
    task_type: str,
    original_parameters: dict,
    context: dict,
) -> dict:
    """Get suggested adaptation parameters based on learned patterns."""
    from skill_fragment_engine.services.transfer_learning_service import get_transfer_learning_service
    
    tl_svc = get_transfer_learning_service()
    suggestions = await tl_svc.suggest_adaptation(task_type, original_parameters, context)
    return suggestions


# Clustering

_clustering_service_instance = None

def get_clustering_service():
    """Get clustering service instance."""
    global _clustering_service_instance
    if _clustering_service_instance is None:
        from skill_fragment_engine.retrieval.clustering import ClusteringService
        settings = get_settings()
        _clustering_service_instance = ClusteringService(
            method=getattr(settings, 'clustering_method', 'auto')
        )
    return _clustering_service_instance


@router.post(
    "/clustering/run",
    response_model=dict,
    tags=["Clustering"],
)
async def run_clustering(
    task_type: str | None = None,
    method: str | None = None,
) -> dict:
    """
    Run clustering on all stored fragments.
    
    Query Parameters:
    - task_type: (optional) Filter fragments by task type
    - method: (optional) Clustering method (auto, kmeans, dbscan, hierarchical)
    
    Returns cluster assignments for all fragments.
    """
    from skill_fragment_engine.retrieval.vector_store import VectorStore
    from skill_fragment_engine.store import FragmentStore
    
    vector_store = VectorStore()
    fragment_store = FragmentStore()
    
    if fragment_store.count() == 0:
        return {"message": "No fragments to cluster", "clusters": []}
    
    embeddings = {}
    fragment_ids = []
    
    for fid in fragment_store._data.keys():
        rec = fragment_store._data[fid]
        if task_type and rec.get("task_type") != task_type:
            continue
        
        frag_raw = rec.get("fragment")
        if not frag_raw:
            continue
        
        embedding = vector_store.get(fid)
        if embedding:
            embeddings[fid] = embedding
            fragment_ids.append(fid)
    
    if not embeddings:
        return {"message": "No embeddings found for clustering", "clusters": []}
    
    clustering_svc = get_clustering_service()
    cluster_mapping = clustering_svc.cluster_fragments(embeddings, method)
    
    n_clusters = len(set(cluster_mapping.values()))
    
    logger.info("clustering_completed", 
               n_fragments=len(cluster_mapping),
               n_clusters=n_clusters)
    
    return {
        "message": f"Clustered {len(cluster_mapping)} fragments into {n_clusters} clusters",
        "n_fragments": len(cluster_mapping),
        "n_clusters": n_clusters,
        "method": method or "auto",
        "cluster_mapping": cluster_mapping,
    }


@router.get(
    "/clustering/info",
    response_model=list[dict],
    tags=["Clustering"],
)
async def get_cluster_info(
    task_type: str | None = None,
) -> list[dict]:
    """Get detailed information about clusters."""
    from skill_fragment_engine.retrieval.vector_store import VectorStore
    from skill_fragment_engine.store import FragmentStore
    
    vector_store = VectorStore()
    fragment_store = FragmentStore()
    
    if fragment_store.count() == 0:
        return []
    
    embeddings = {}
    for fid in fragment_store._data.keys():
        rec = fragment_store._data[fid]
        if task_type and rec.get("task_type") != task_type:
            continue
        
        embedding = vector_store.get(fid)
        if embedding:
            embeddings[fid] = embedding
    
    if not embeddings:
        return []
    
    clustering_svc = get_clustering_service()
    clustering_svc.cluster_fragments(embeddings)
    
    cluster_info = clustering_svc.get_cluster_info(embeddings)
    
    return cluster_info


@router.get(
    "/clustering/{fragment_id}/similar",
    response_model=list[dict],
    tags=["Clustering"],
)
async def get_similar_in_cluster(
    fragment_id: str,
    limit: int = 10,
) -> list[dict]:
    """Find similar fragments within the same cluster."""
    from skill_fragment_engine.retrieval.vector_store import VectorStore
    from skill_fragment_engine.store import FragmentStore
    
    vector_store = VectorStore()
    fragment_store = FragmentStore()
    
    if fragment_store.count() == 0:
        return []
    
    embeddings = {}
    for fid in fragment_store._data.keys():
        embedding = vector_store.get(fid)
        if embedding:
            embeddings[fid] = embedding
    
    if not embeddings or fragment_id not in embeddings:
        return []
    
    clustering_svc = get_clustering_service()
    cluster_mapping = clustering_svc.cluster_fragments(embeddings)
    
    target_cluster = cluster_mapping.get(fragment_id)
    if target_cluster is None:
        return []
    
    similar = [
        fid for fid, cid in cluster_mapping.items()
        if cid == target_cluster and fid != fragment_id
    ][:limit]
    
    result = []
    for fid in similar:
        rec = fragment_store._data.get(fid)
        if rec:
            result.append({
                "fragment_id": fid,
                "task_type": rec.get("task_type"),
                "prompt": rec.get("prompt", "")[:100],
            })
    
    return result
