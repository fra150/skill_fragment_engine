"""Tests for core models."""

import pytest
from datetime import datetime

from skill_fragment_engine.core.models import (
    SkillFragment,
    FragmentPattern,
    Variant,
    InputSignature,
    OutputSchema,
    FragmentMetrics,
    TaskType,
    Decision,
)
from skill_fragment_engine.core.enums import PatternType, ValidationOutcome


class TestInputSignature:
    """Tests for InputSignature model."""

    def test_create_from_prompt(self):
        """Test creating signature from prompt."""
        sig = InputSignature.create(
            prompt="Write a function",
            context={"language": "python"},
            parameters={"style": "functional"}
        )

        assert sig.prompt_hash is not None
        assert sig.context_hash is not None
        assert len(sig.prompt_hash) == 64  # SHA-256 hex length

    def test_matches_identical(self):
        """Test that identical inputs match."""
        sig1 = InputSignature.create(
            prompt="Write a function",
            context={"language": "python"},
        )
        sig2 = InputSignature.create(
            prompt="Write a function",
            context={"language": "python"},
        )

        assert sig1.matches(sig2)

    def test_different_prompts_dont_match(self):
        """Test that different prompts don't match."""
        sig1 = InputSignature.create(prompt="Function A")
        sig2 = InputSignature.create(prompt="Function B")

        assert not sig1.matches(sig2)


class TestFragmentMetrics:
    """Tests for FragmentMetrics model."""

    def test_total_uses(self):
        """Test total uses calculation."""
        metrics = FragmentMetrics(
            reuse_count=10,
            adapt_count=5,
            failure_count=2
        )

        assert metrics.total_uses == 15

    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = FragmentMetrics(
            reuse_count=8,
            adapt_count=4,
            failure_count=3
        )

        assert metrics.success_rate == 12 / 15

    def test_zero_uses_success_rate(self):
        """Test success rate with zero uses."""
        metrics = FragmentMetrics()

        assert metrics.success_rate == 1.0


class TestSkillFragment:
    """Tests for SkillFragment model."""

    def test_create_fragment(self):
        """Test creating a fragment."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(
                prompt="Write a function",
                context={"language": "python"}
            ),
            output_schema=OutputSchema(
                result="def reverse(s): return s[::-1]",
                process_steps=["analyze", "generate"]
            )
        )

        assert fragment.fragment_id is not None
        assert fragment.task_type == TaskType.CODE_GENERATION
        assert fragment.decay_score == 1.0
        assert fragment.is_active is True

    def test_add_validation_reuse(self):
        """Test adding reuse validation."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output")
        )

        from skill_fragment_engine.core.models import ValidationRecord

        record = ValidationRecord(
            fragment_id=fragment.fragment_id,
            outcome=ValidationOutcome.REUSED_SUCCESSFULLY,
            context_distance=0.05,
            cost_saved=0.020
        )

        initial_count = fragment.metrics.reuse_count
        fragment.add_validation(record)

        assert fragment.metrics.reuse_count == initial_count + 1
        assert fragment.metrics.total_cost_saved == 0.020


class TestFragmentPattern:
    """Tests for FragmentPattern model."""

    def test_create_pattern(self):
        """Test creating a pattern."""
        pattern = FragmentPattern(
            type=PatternType.ALGORITHM,
            content="def reverse(s): return s[::-1]",
            abstraction_level=0.8,
            confidence=0.95
        )

        assert pattern.pattern_id is not None
        assert pattern.type == PatternType.ALGORITHM
        assert pattern.abstraction_level == 0.8
