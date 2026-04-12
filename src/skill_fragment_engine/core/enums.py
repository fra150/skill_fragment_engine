"""Core domain models for Skill Fragment Engine."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TaskType(str, Enum):
    """Supported task types."""

    CODE_GENERATION = "code_generation"
    TEXT_SUMMARIZATION = "text_summarization"
    DATA_EXTRACTION = "data_extraction"
    CLASSIFICATION = "classification"
    TRANSLATION = "translation"
    QUESTION_ANSWERING = "question_answering"


class Decision(str, Enum):
    """Execution decision from validator."""

    REUSE = "reuse"
    ADAPT = "adapt"
    RECOMPUTE = "recompute"


class PatternType(str, Enum):
    """Types of fragment patterns."""

    ALGORITHM = "algorithm"
    TEMPLATE = "template"
    STRUCTURE = "structure"
    HEURISTIC = "heuristic"


class ValidationOutcome(str, Enum):
    """Outcome of fragment validation."""

    REUSED_SUCCESSFULLY = "reused_successfully"
    ADAPTED = "adapted"
    FAILED = "failed"
    RECOMPUTED = "recomputed"


class VariantCreationReason(str, Enum):
    """Why a variant was created."""

    ADAPTATION = "adaptation"
    FAILURE_RECOVERY = "failure_recovery"
    MANUAL_IMPROVEMENT = "manual_improvement"


class ValidationResult(str, Enum):
    """Validation result for variants."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"



# Input/Output Schemas



class InputSignature(BaseModel):
    """Hash-based signature of the input."""

    prompt_hash: str = Field(..., description="SHA-256 hash of prompt")
    context_hash: str = Field(..., description="SHA-256 hash of context")
    parameters: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        prompt: str,
        context: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> InputSignature:
        """Create signature from raw input."""
        context = context or {}
        parameters = parameters or {}

        return cls(
            prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(),
            context_hash=hashlib.sha256(
                json.dumps(context, sort_keys=True).encode()
            ).hexdigest(),
            parameters=parameters,
        )

    def matches(self, other: InputSignature) -> bool:
        """Check if signatures match exactly."""
        return (
            self.prompt_hash == other.prompt_hash
            and self.context_hash == other.context_hash
            and self.parameters == other.parameters
        )


class FragmentPattern(BaseModel):
    """Reusable sub-component extracted from execution."""

    pattern_id: UUID = Field(default_factory=uuid4)
    fragment_id: UUID | None = Field(default=None, description="Parent fragment")
    type: PatternType
    content: str
    abstraction_level: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="0.0=specific, 1.0=generalizable"
    )
    dependencies: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tested_on: list[UUID] = Field(default_factory=list)


class OutputSchema(BaseModel):
    """Schema for execution output."""

    result: Any = Field(..., description="Complete output")
    fragment_patterns: list[FragmentPattern] = Field(default_factory=list)
    process_steps: list[str] = Field(default_factory=list)
    output_hash: str | None = Field(default=None, description="SHA-256 hash of result")

    @field_validator("output_hash", mode="before")
    @classmethod
    def compute_hash(cls, v: str | None, info) -> str:
        """Compute hash if not provided."""
        if v is None:
            result = info.data.get("result")
            if result is not None:
                return hashlib.sha256(
                    json.dumps(result, sort_keys=True, default=str).encode()
                ).hexdigest()
        return v or ""



# Metrics & Tracking



class FragmentMetrics(BaseModel):
    """Metrics for a skill fragment."""

    creation_cost: float = Field(default=0.0, ge=0.0, description="Cost to create ($)")
    creation_latency: float = Field(
        default=0.0, ge=0.0, description="Creation time (seconds)"
    )
    reuse_count: int = Field(default=0, ge=0)
    adapt_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    avg_adaptation_cost: float = Field(default=0.0, ge=0.0)
    total_cost_saved: float = Field(default=0.0, ge=0.0)

    @property
    def total_uses(self) -> int:
        """Total number of uses."""
        return self.reuse_count + self.adapt_count

    @property
    def success_rate(self) -> float:
        """Rate of successful uses."""
        total = self.total_uses + self.failure_count
        if total == 0:
            return 1.0
        return self.total_uses / total


class ValidationRecord(BaseModel):
    """Record of a validation attempt."""

    record_id: UUID = Field(default_factory=uuid4)
    fragment_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validation_type: str = Field(
        default="context_comparison",
        description="Type of validation performed"
    )
    context_distance: float = Field(default=0.0, ge=0.0, le=1.0)
    outcome: ValidationOutcome
    cost_saved: float = Field(default=0.0)
    latency_saved: float = Field(default=0.0, description="Latency saved (seconds)")



# Core Entities



class SkillFragment(BaseModel):
    """
    Complete record of an AI execution.

    This is the core entity representing a cached skill that can be
    validated and reused for future similar tasks.
    """

    fragment_id: UUID = Field(default_factory=uuid4)
    task_type: TaskType

    # Input signature
    input_signature: InputSignature

    # Output schema
    output_schema: OutputSchema

    # Embedding vector (stored separately in FAISS, referenced here)
    embedding_id: str | None = Field(default=None)

    # Validation history
    validation_history: list[ValidationRecord] = Field(default_factory=list)

    # Metrics
    metrics: FragmentMetrics = Field(default_factory=FragmentMetrics)

    # Versioning
    version_chain: list[UUID] = Field(default_factory=list)
    variants: list[UUID] = Field(default_factory=list)
    parent_id: UUID | None = Field(default=None, description="Parent fragment if variant")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decay_score: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Freshness/reliability score"
    )
    quality_score: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Quality assessment"
    )
    is_active: bool = Field(default=True)

    class Config:
        """Pydantic config."""

        use_enum_values = True

    def add_validation(self, record: ValidationRecord) -> None:
        """Add validation record and update metrics."""
        self.validation_history.append(record)
        self.updated_at = datetime.now(timezone.utc)

        # Update metrics based on outcome
        if record.outcome == ValidationOutcome.REUSED_SUCCESSFULLY:
            self.metrics.reuse_count += 1
            self.metrics.total_cost_saved += record.cost_saved
        elif record.outcome == ValidationOutcome.ADAPTED:
            self.metrics.adapt_count += 1
        elif record.outcome == ValidationOutcome.FAILED:
            self.metrics.failure_count += 1


class Variant(BaseModel):
    """
    Alternative version of a fragment.

    Created through adaptation, failure recovery, or manual improvement.
    """

    variant_id: UUID = Field(default_factory=uuid4)
    parent_fragment_id: UUID
    created_from: VariantCreationReason

    # Change tracking
    diff_type: str = Field(
        default="parameter_override",
        description="Type of change made"
    )
    before_snapshot: dict[str, Any] = Field(default_factory=dict)
    after_snapshot: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    reason: str
    validation_result: ValidationResult = Field(default=ValidationResult.PENDING)
    performance_delta: dict[str, float] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality_score: float = Field(default=0.5, ge=0.0, le=1.0)

    class Config:
        """Pydantic config."""

        use_enum_values = True



# API Request/Response Models



class ExecutionRequest(BaseModel):
    """Request to execute a task through SFE."""

    task_type: TaskType
    prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic config."""

        use_enum_values = True

    @property
    def allow_adaptation(self) -> bool:
        """Whether adaptation is allowed."""
        return self.options.get("allow_adaptation", True)

    @property
    def allow_recompute(self) -> bool:
        """Whether recompute is allowed."""
        return self.options.get("allow_recompute", True)

    @property
    def capture_fragment(self) -> bool:
        """Whether to capture result as fragment."""
        return self.options.get("capture_fragment", True)


class ExecutionMetadata(BaseModel):
    """Metadata about an execution."""

    execution_id: UUID
    decision: Decision
    fragment_id: UUID | None = None
    variant_id: UUID | None = None
    cost: float = 0.0
    latency_ms: float = 0.0
    cost_saved: float = 0.0
    decision_reason: str = ""


class ExecutionResponse(BaseModel):
    """Response from execution."""

    execution_id: UUID
    decision: Decision
    result: Any
    metadata: ExecutionMetadata

    class Config:
        """Pydantic config."""

        use_enum_values = True


class FeedbackType(str, Enum):
    """Type of feedback from users."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class FeedbackCategory(str, Enum):
    """Category of feedback."""

    QUALITY = "quality"
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    PERFORMANCE = "performance"
    USABILITY = "usability"


class UserFeedback(BaseModel):
    """Feedback from users on fragment execution."""

    feedback_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID | None = Field(default=None, description="Related execution ID")
    fragment_id: UUID | None = Field(default=None, description="Related fragment ID")
    variant_id: UUID | None = Field(default=None, description="Related variant ID")
    
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    category: FeedbackCategory = Field(default=FeedbackCategory.QUALITY)
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Quality score 0-1")
    
    comment: str = Field(default="", description="User comment")
    expected_output: str | None = Field(default=None, description="What user expected")
    actual_output: str | None = Field(default=None, description="What user got")
    
    user_id: str | None = Field(default=None, description="Optional user identifier")
    session_id: str | None = Field(default=None, description="Session identifier")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed: bool = Field(default=False, description="Whether feedback has been processed")

    class Config:
        """Pydantic config."""

        use_enum_values = True
