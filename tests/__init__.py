"""Unit tests for SFE."""

import pytest


@pytest.fixture
def sample_prompt():
    """Sample prompt for testing."""
    return "Write a function to reverse a string in Python"


@pytest.fixture
def sample_context():
    """Sample context for testing."""
    return {"language": "python", "style": "functional"}


@pytest.fixture
def sample_parameters():
    """Sample parameters for testing."""
    return {"include_type_hints": True}
