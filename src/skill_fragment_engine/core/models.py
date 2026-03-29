"""Core models for Skill Fragment Engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skill_fragment_engine.core.enums import (
    Decision,
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResponse,
    FragmentMetrics,
    FragmentPattern,
    InputSignature,
    OutputSchema,
    PatternType,
    SkillFragment,
    TaskType,
    ValidationOutcome,
    ValidationRecord,
    ValidationResult,
    VariantCreationReason,
    Variant,
)


@dataclass
class MatchCandidate:
    """A candidate fragment from retrieval."""

    fragment_id: str
    score: float
    match_type: str
    input_signature: dict[str, Any] | None = None


__all__ = [
    "Decision",
    "ExecutionMetadata",
    "ExecutionRequest",
    "ExecutionResponse",
    "FragmentMetrics",
    "FragmentPattern",
    "InputSignature",
    "MatchCandidate",
    "OutputSchema",
    "PatternType",
    "SkillFragment",
    "TaskType",
    "ValidationOutcome",
    "ValidationRecord",
    "ValidationResult",
    "VariantCreationReason",
    "Variant",
]
