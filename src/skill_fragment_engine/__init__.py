"""
Skill Fragment Engine (SFE)

A cognitive cache layer for AI agents with verified skill reuse.
"""

__version__ = "1.0.0"

from skill_fragment_engine.core.models import SkillFragment, FragmentPattern, Variant
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.retrieval.matcher import SkillMatcherLayer
from skill_fragment_engine.validation.validator import ValidatorEngine

__all__ = [
    "SkillFragment",
    "FragmentPattern",
    "Variant",
    "ExecutionEngine",
    "SkillMatcherLayer",
    "ValidatorEngine",
]
