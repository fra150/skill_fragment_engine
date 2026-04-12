"""Pydantic schemas for API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from skill_fragment_engine.core.enums import TaskType, Decision, FeedbackType, FeedbackCategory


# Request Schemas

class ExecuteRequest(BaseModel):
    """Request to execute a task."""

    task_type: TaskType
    prompt: str = Field(..., min_length=1, max_length=10000)
    context: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic config."""
        use_enum_values = True


class FragmentCreateRequest(BaseModel):
    """Request to create a fragment manually."""

    task_type: TaskType
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: Any
    patterns: list[dict[str, Any]] = Field(default_factory=list)


class FragmentSearchRequest(BaseModel):
    """Request to search fragments."""

    query: str = Field(..., min_length=1, max_length=5000)
    task_type: TaskType | None = None
    top_k: int = Field(default=5, ge=1, le=100)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)

    class Config:
        """Pydantic config."""
        use_enum_values = True


class ValidationRequest(BaseModel):
    """Request to validate a fragment."""

    fragment_id: UUID
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)

# Response Schemas

class ExecutionMetadataResponse(BaseModel):
    """Metadata about an execution."""

    execution_id: UUID
    decision: Decision
    fragment_id: UUID | None = None
    variant_id: UUID | None = None
    cost: float
    latency_ms: float
    cost_saved: float
    decision_reason: str


class ExecutionResponse(BaseModel):
    """Response from execution."""

    execution_id: UUID
    decision: Decision
    result: Any
    metadata: ExecutionMetadataResponse

    class Config:
        """Pydantic config."""
        use_enum_values = True


class FragmentPatternResponse(BaseModel):
    """Fragment pattern response."""

    pattern_id: UUID
    type: str
    content: str
    abstraction_level: float
    confidence: float


class FragmentMetricsResponse(BaseModel):
    """Fragment metrics response."""

    creation_cost: float
    creation_latency: float
    reuse_count: int
    adapt_count: int
    failure_count: int
    total_cost_saved: float

class FragmentResponse(BaseModel):
    """Fragment response."""

    fragment_id: UUID
    task_type: str
    prompt_hash: str
    context_hash: str
    result: Any
    patterns: list[FragmentPatternResponse]
    metrics: FragmentMetricsResponse
    decay_score: float
    quality_score: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    reuse_count: int = 0

    class Config:
        """Pydantic config."""
        from_attributes = True

class FragmentSearchResponse(BaseModel):
    """Fragment search response."""

    fragment_id: UUID
    score: float
    task_type: str

class MetricsResponse(BaseModel):
    """System metrics response."""

    total_fragments: int
    active_fragments: int
    reuse_rate: float
    avg_cost_per_request: float
    total_cost_saved: float
    latency_p50_ms: float
    latency_p99_ms: float

class PruningResponse(BaseModel):
    """Pruning operation response."""

    success: bool
    total_removed: int
    decay_removals: int
    duplicate_removals: int
    stale_removals: int
    low_quality_removals: int
    failure_removals: int

class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime

# Error Schemas

class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
    code: str | None = None


class FeedbackRequest(BaseModel):
    """Request to submit feedback on a fragment execution."""

    execution_id: UUID | None = Field(default=None, description="Related execution ID")
    fragment_id: UUID | None = Field(default=None, description="Related fragment ID")
    variant_id: UUID | None = Field(default=None, description="Related variant ID")
    
    feedback_type: FeedbackType = Field(..., description="Type of feedback: positive, negative, or neutral")
    category: FeedbackCategory = Field(default=FeedbackCategory.QUALITY, description="Feedback category")
    score: float = Field(..., ge=0.0, le=1.0, description="Quality score from 0 to 1")
    
    comment: str = Field(default="", description="Optional user comment")
    expected_output: str | None = Field(default=None, description="What user expected")
    actual_output: str | None = Field(default=None, description="What user got")
    
    user_id: str | None = Field(default=None, description="Optional user identifier")
    session_id: str | None = Field(default=None, description="Session identifier")

    class Config:
        """Pydantic config."""
        use_enum_values = True


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""

    feedback_id: UUID
    success: bool
    message: str


class FeedbackStatsResponse(BaseModel):
    """Feedback statistics response."""

    total_feedback: int
    average_score: float
    positive_count: int
    negative_count: int
    neutral_count: int
    category_breakdown: dict[str, int]
    positive_ratio: float
    negative_ratio: float
