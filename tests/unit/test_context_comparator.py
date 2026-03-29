"""Tests for context comparator."""

import pytest

from skill_fragment_engine.validation.context_comparator import (
    ContextComparator,
    compute_embedding_distance,
)


class TestContextComparator:
    """Tests for ContextComparator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.comparator = ContextComparator()

    def test_identical_contexts(self):
        """Test comparison of identical contexts."""
        input_a = {
            "prompt": "Write a function",
            "context": {"language": "python"},
            "parameters": {"style": "functional"}
        }
        input_b = {
            "prompt": "Write a function",
            "context": {"language": "python"},
            "parameters": {"style": "functional"}
        }

        distance = self.comparator.compute_distance(input_a, input_b)

        assert distance == 0.0

    def test_different_prompts(self):
        """Test comparison of different prompts."""
        input_a = {"prompt": "Write a function"}
        input_b = {"prompt": "Read a file"}

        distance = self.comparator.compute_distance(input_a, input_b)

        assert distance > 0.0
        assert distance <= 1.0

    def test_different_contexts(self):
        """Test comparison of different contexts."""
        input_a = {"context": {"language": "python"}}
        input_b = {"context": {"language": "javascript"}}

        distance = self.comparator.compute_distance(input_a, input_b)

        assert distance > 0.0
        assert distance <= 1.0

    def test_different_parameters(self):
        """Test comparison of different parameters."""
        input_a = {"parameters": {"max_length": 100}}
        input_b = {"parameters": {"max_length": 500}}

        distance = self.comparator.compute_distance(input_a, input_b)

        assert distance > 0.0
        assert distance <= 1.0

    def test_missing_context(self):
        """Test comparison with missing context."""
        input_a = {"context": {"language": "python"}}
        input_b = {}

        distance = self.comparator.compute_distance(input_a, input_b)

        assert distance > 0.0

    def test_nested_context(self):
        """Test comparison of nested contexts."""
        input_a = {
            "context": {
                "settings": {
                    "max_length": 100,
                    "temperature": 0.7
                }
            }
        }
        input_b = {
            "context": {
                "settings": {
                    "max_length": 100,
                    "temperature": 0.7
                }
            }
        }

        distance = self.comparator.compute_distance(input_a, input_b)

        assert distance == 0.0


class TestComputeEmbeddingDistance:
    """Tests for embedding distance computation."""

    def test_identical_embeddings(self):
        """Test distance of identical embeddings."""
        embedding = [0.1, 0.2, 0.3, 0.4]

        distance = compute_embedding_distance(embedding, embedding)

        assert distance == 0.0

    def test_opposite_embeddings(self):
        """Test distance of opposite embeddings."""
        embedding_a = [1.0, 1.0, 1.0, 1.0]
        embedding_b = [-1.0, -1.0, -1.0, -1.0]

        distance = compute_embedding_distance(embedding_a, embedding_b)

        assert distance == pytest.approx(1.0, rel=0.01)

    def test_orthogonal_embeddings(self):
        """Test distance of orthogonal embeddings."""
        embedding_a = [1.0, 0.0, 0.0, 0.0]
        embedding_b = [0.0, 1.0, 0.0, 0.0]

        distance = compute_embedding_distance(embedding_a, embedding_b)

        assert distance == pytest.approx(1.0, rel=0.01)

    def test_similar_embeddings(self):
        """Test distance of similar embeddings."""
        embedding_a = [1.0, 0.5, 0.3, 0.1]
        embedding_b = [0.9, 0.4, 0.35, 0.15]

        distance = compute_embedding_distance(embedding_a, embedding_b)

        assert 0.0 < distance < 1.0
