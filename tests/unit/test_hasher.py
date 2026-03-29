"""Tests for input hasher."""

import pytest

from skill_fragment_engine.retrieval.hasher import InputHasher


class TestInputHasher:
    """Tests for InputHasher class."""

    def test_hash_prompt(self):
        """Test prompt hashing."""
        hash1 = InputHasher.hash_prompt("Hello world")
        hash2 = InputHasher.hash_prompt("Hello world")
        hash3 = InputHasher.hash_prompt("Hello World")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 64  # SHA-256 hex

    def test_hash_context(self):
        """Test context hashing."""
        context1 = {"language": "python", "style": "functional"}
        context2 = {"language": "python", "style": "functional"}
        context3 = {"language": "javascript"}

        hash1 = InputHasher.hash_context(context1)
        hash2 = InputHasher.hash_context(context2)
        hash3 = InputHasher.hash_context(context3)

        assert hash1 == hash2
        assert hash1 != hash3

    def test_hash_context_order_independent(self):
        """Test that context hashing is order-independent."""
        context1 = {"a": 1, "b": 2, "c": 3}
        context2 = {"c": 3, "a": 1, "b": 2}

        assert InputHasher.hash_context(context1) == InputHasher.hash_context(context2)

    def test_hash_context_none(self):
        """Test hashing None context."""
        hash1 = InputHasher.hash_context(None)
        hash2 = InputHasher.hash_context({})

        # Both should produce same hash for empty context
        assert hash1 == hash2

    def test_hash_parameters(self):
        """Test parameters hashing."""
        params1 = {"max_length": 100, "temperature": 0.7}
        params2 = {"max_length": 100, "temperature": 0.7}

        assert InputHasher.hash_parameters(params1) == InputHasher.hash_parameters(params2)

    def test_hash_input_combined(self):
        """Test combined input hashing."""
        hash1 = InputHasher.hash_input(
            prompt="Write code",
            context={"language": "python"},
            parameters={"style": "functional"}
        )
        hash2 = InputHasher.hash_input(
            prompt="Write code",
            context={"language": "python"},
            parameters={"style": "functional"}
        )

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_hash_output(self):
        """Test output hashing."""
        output1 = {"code": "def foo(): pass"}
        output2 = {"code": "def foo(): pass"}

        assert InputHasher.hash_output(output1) == InputHasher.hash_output(output2)

    def test_hash_output_dict_order_independent(self):
        """Test that output hashing is order-independent."""
        output1 = {"a": 1, "b": 2}
        output2 = {"b": 2, "a": 1}

        assert InputHasher.hash_output(output1) == InputHasher.hash_output(output2)
