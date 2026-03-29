"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

import pytest

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


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
