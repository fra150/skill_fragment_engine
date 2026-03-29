"""Tests for governance components."""

import pytest
from datetime import datetime, timedelta

from skill_fragment_engine.core.models import (
    SkillFragment,
    FragmentMetrics,
    InputSignature,
    OutputSchema,
    TaskType,
)
from skill_fragment_engine.governance.decay_manager import DecayManager
from skill_fragment_engine.governance.scoring_calculator import ScoringCalculator


class TestDecayManager:
    """Tests for DecayManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = DecayManager()

    def test_fresh_fragment_full_score(self):
        """Test that fresh fragment has full decay score."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output")
        )
        # Fragment just created, so age is 0
        fragment.created_at = datetime.utcnow()

        score = self.manager.calculate_decay_score(fragment)

        assert score == pytest.approx(1.0, rel=0.1)

    def test_old_fragment_decays(self):
        """Test that old fragment decays."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output")
        )
        # Set age to 90 days (half-life for code_generation)
        fragment.created_at = datetime.utcnow() - timedelta(days=90)

        score = self.manager.calculate_decay_score(fragment)

        assert score < 1.0
        assert score >= 0.5  # Should be around 0.5 (half-life)

    def test_should_prune_never_used_old(self):
        """Test that never-used old fragments should be pruned."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output"),
            metrics=FragmentMetrics(reuse_count=0, adapt_count=0, failure_count=0)
        )
        fragment.created_at = datetime.utcnow() - timedelta(days=60)

        should_prune = self.manager.should_prune(fragment)

        assert should_prune is True

    def test_should_not_prune_recently_used(self):
        """Test that recently used fragments should not be pruned."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output"),
            metrics=FragmentMetrics(reuse_count=10, adapt_count=2, failure_count=0)
        )
        fragment.created_at = datetime.utcnow() - timedelta(days=60)

        should_prune = self.manager.should_prune(fragment)

        assert should_prune is False


class TestScoringCalculator:
    """Tests for ScoringCalculator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = ScoringCalculator()

    def test_inactive_fragment_zero_score(self):
        """Test that inactive fragments get zero score."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output"),
            is_active=False
        )

        score = self.calculator.calculate_fragment_score(fragment)

        assert score == 0.0

    def test_fresh_active_fragment_positive_score(self):
        """Test that active fragment gets positive score."""
        fragment = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output"),
            is_active=True,
            decay_score=1.0,
            quality_score=0.8
        )

        score = self.calculator.calculate_fragment_score(fragment)

        assert score > 0.0
        assert score <= 1.0

    def test_high_reuse_fragment_better_score(self):
        """Test that high-reuse fragment gets better score."""
        fragment_low = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output"),
            metrics=FragmentMetrics(reuse_count=1, adapt_count=0)
        )
        fragment_high = SkillFragment(
            task_type=TaskType.CODE_GENERATION,
            input_signature=InputSignature.create(prompt="test"),
            output_schema=OutputSchema(result="output"),
            metrics=FragmentMetrics(reuse_count=100, adapt_count=10)
        )

        score_low = self.calculator.calculate_fragment_score(fragment_low)
        score_high = self.calculator.calculate_fragment_score(fragment_high)

        assert score_high > score_low

    def test_rank_fragments(self):
        """Test ranking fragments."""
        fragments = [
            SkillFragment(
                task_type=TaskType.CODE_GENERATION,
                input_signature=InputSignature.create(prompt=f"test_{i}"),
                output_schema=OutputSchema(result="output"),
                metrics=FragmentMetrics(reuse_count=100 - i * 10)
            )
            for i in range(5)
        ]

        ranked = self.calculator.rank_fragments(fragments)

        # Should be sorted by score descending
        scores = [self.calculator.calculate_fragment_score(f) for f in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_get_top_for_task_type(self):
        """Test getting top fragments for task type."""
        fragments = [
            SkillFragment(
                task_type=TaskType.CODE_GENERATION,
                input_signature=InputSignature.create(prompt=f"code_{i}"),
                output_schema=OutputSchema(result="output"),
                metrics=FragmentMetrics(reuse_count=100 - i)
            )
            for i in range(10)
        ] + [
            SkillFragment(
                task_type=TaskType.TEXT_SUMMARIZATION,
                input_signature=InputSignature.create(prompt=f"text_{i}"),
                output_schema=OutputSchema(result="output"),
                metrics=FragmentMetrics(reuse_count=50 - i)
            )
            for i in range(5)
        ]

        top_code = self.calculator.get_top_for_task_type(
            fragments,
            TaskType.CODE_GENERATION,
            top_k=3
        )

        assert len(top_code) == 3
        assert all(f.task_type == TaskType.CODE_GENERATION for f in top_code)
