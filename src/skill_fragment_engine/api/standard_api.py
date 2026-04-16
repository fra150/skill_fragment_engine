from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class FragmentInput(BaseModel):
    task_type: str
    prompt: str
    context: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)


class FragmentOutput(BaseModel):
    decision: str
    output: str
    fragment_id: Optional[str] = None
    cost_saved: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FragmentSearchRequest(BaseModel):
    query: str
    top_k: int = 10
    min_score: float = 0.5
    filters: Optional[Dict[str, Any]] = None


class FragmentSearchResponse(BaseModel):
    fragments: List[Dict[str, Any]]
    total: int
    query_time_ms: float


class FragmentCreateRequest(BaseModel):
    task_type: str
    prompt: str
    output: str
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FragmentResponse(BaseModel):
    id: str
    task_type: str
    prompt: str
    output: str
    context: Dict[str, Any]
    created_at: str
    version: str
    quality_score: Optional[float] = None


class ClusteringRequest(BaseModel):
    method: str = "auto"
    min_clusters: int = 2
    max_clusters: int = 50


class ClusteringResponse(BaseModel):
    clusters: Dict[str, int]
    centroids: Dict[str, List[float]]
    method: str
    num_clusters: int


class FeedbackRequest(BaseModel):
    fragment_id: str
    feedback_type: str
    score: float = Field(ge=0.0, le=1.0)
    comment: Optional[str] = None
    category: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: str
    fragment_id: str
    feedback_type: str
    score: float
    created_at: str


class MetricsResponse(BaseModel):
    total_requests: int
    reuse_count: int
    adapt_count: int
    recompute_count: int
    hit_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    active_fragments: int
    memory_usage_mb: float
    cost_saved: float


class VersionResponse(BaseModel):
    fragment_id: str
    versions: List[Dict[str, Any]]
    current_version: str


class RollbackRequest(BaseModel):
    fragment_id: str
    version: str
    strategy: str = "restore"


class RollbackResponse(BaseModel):
    success: bool
    fragment_id: str
    version: str
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    plugins_loaded: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


SFE_API_MODELS = {
    "FragmentInput": FragmentInput,
    "FragmentOutput": FragmentOutput,
    "FragmentSearchRequest": FragmentSearchRequest,
    "FragmentSearchResponse": FragmentSearchResponse,
    "FragmentCreateRequest": FragmentCreateRequest,
    "FragmentResponse": FragmentResponse,
    "ClusteringRequest": ClusteringRequest,
    "ClusteringResponse": ClusteringResponse,
    "FeedbackRequest": FeedbackRequest,
    "FeedbackResponse": FeedbackResponse,
    "MetricsResponse": MetricsResponse,
    "VersionResponse": VersionResponse,
    "RollbackRequest": RollbackRequest,
    "RollbackResponse": RollbackResponse,
    "HealthResponse": HealthResponse,
    "ErrorResponse": ErrorResponse,
}
