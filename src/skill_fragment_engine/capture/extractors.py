"""Pattern extractors for different task types."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import structlog

from skill_fragment_engine.core.models import FragmentPattern, PatternType

logger = structlog.get_logger(__name__)


class BaseExtractor(ABC):
    """Base class for pattern extractors."""

    @abstractmethod
    async def extract(self, output: Any, task_type: str) -> list[FragmentPattern]:
        """
        Extract reusable patterns from output.

        Args:
            output: The execution output
            task_type: Type of task

        Returns:
            List of extracted patterns
        """
        pass


class CodeExtractor(BaseExtractor):
    """Extracts patterns from code generation output."""

    async def extract(self, output: Any, task_type: str) -> list[FragmentPattern]:
        """Extract code patterns from output."""
        if not isinstance(output, str):
            # Try to extract from dict
            if isinstance(output, dict):
                output = output.get("code", "") or output.get("result", "")

        if not isinstance(output, str):
            return []

        patterns = []

        # Extract function definitions
        functions = self._extract_functions(output)
        for func in functions:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.ALGORITHM,
                content=func,
                abstraction_level=0.7,
                confidence=0.85,
            ))

        # Extract class definitions
        classes = self._extract_classes(output)
        for cls in classes:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.STRUCTURE,
                content=cls,
                abstraction_level=0.6,
                confidence=0.80,
            ))

        # Extract imports
        imports = self._extract_imports(output)
        for imp in imports:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.TEMPLATE,
                content=imp,
                abstraction_level=0.9,
                confidence=0.95,
            ))

        return patterns

    def _extract_functions(self, code: str) -> list[str]:
        """Extract function definitions."""
        import re

        patterns = [
            r"def\s+\w+\s*\([^)]*\)\s*:",  # Python
            r"function\s+\w+\s*\([^)]*\)\s*{",  # JavaScript
            r"public\s+\w+\s+\w+\s*\([^)]*\)\s*{",  # Java
            r"func\s+\w+\s*\([^)]*\)\s*{",  # Go
        ]

        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, code)
            functions.extend(matches)

        return functions

    def _extract_classes(self, code: str) -> list[str]:
        """Extract class definitions."""
        import re

        patterns = [
            r"class\s+\w+(\s*\([^)]*\))?\s*:",  # Python
            r"class\s+\w+\s*{",  # JavaScript/Java
            r"struct\s+\w+\s*{",  # Go/C
        ]

        classes = []
        for pattern in patterns:
            matches = re.findall(pattern, code)
            classes.extend(matches)

        return classes

    def _extract_imports(self, code: str) -> list[str]:
        """Extract import statements."""
        import re

        patterns = [
            r"^import\s+.+$",  # Python/JavaScript
            r"^from\s+.+\s+import\s+.+$",  # Python
            r"^#include\s*<.+>",  # C/C++
        ]

        imports = []
        for pattern in patterns:
            matches = re.findall(pattern, code, re.MULTILINE)
            imports.extend(matches)

        return list(set(imports))  # Deduplicate


class TextExtractor(BaseExtractor):
    """Extracts patterns from text generation output."""

    async def extract(self, output: Any, task_type: str) -> list[FragmentPattern]:
        """Extract text patterns from output."""
        if not isinstance(output, str):
            if isinstance(output, dict):
                output = output.get("text", "") or output.get("result", "")

        if not isinstance(output, str):
            return []

        patterns = []

        if task_type == "text_summarization":
            patterns.extend(self._extract_summary_patterns(output))
        elif task_type == "translation":
            patterns.extend(self._extract_translation_patterns(output))
        elif task_type == "question_answering":
            patterns.extend(self._extract_qa_patterns(output))
        else:
            patterns.extend(self._extract_generic_patterns(output))

        return patterns

    def _extract_summary_patterns(self, text: str) -> list[FragmentPattern]:
        """Extract patterns from summaries."""
        patterns = []

        # Extract sentence structure
        sentences = text.split(". ")
        if sentences:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.TEMPLATE,
                content=f"Summary with {len(sentences)} key points",
                abstraction_level=0.5,
                confidence=0.75,
            ))

        # Extract key phrases
        key_phrases = self._extract_key_phrases(text)
        for phrase in key_phrases:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.HEURISTIC,
                content=phrase,
                abstraction_level=0.3,
                confidence=0.6,
            ))

        return patterns

    def _extract_translation_patterns(self, text: str) -> list[FragmentPattern]:
        """Extract patterns from translations."""
        patterns = []

        # Extract structural elements
        sentences = text.split(". ")
        patterns.append(FragmentPattern(
            pattern_id=uuid4(),
            type=PatternType.TEMPLATE,
            content=f"Translated text with {len(sentences)} sentences",
            abstraction_level=0.6,
            confidence=0.8,
        ))

        return patterns

    def _extract_qa_patterns(self, text: str) -> list[FragmentPattern]:
        """Extract patterns from Q&A responses."""
        patterns = []

        # Extract answer structure
        if "?" in text:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.TEMPLATE,
                content="Question and answer format",
                abstraction_level=0.7,
                confidence=0.85,
            ))

        return patterns

    def _extract_generic_patterns(self, text: str) -> list[FragmentPattern]:
        """Extract generic text patterns."""
        patterns = []

        # Basic structure
        lines = text.split("\n")
        patterns.append(FragmentPattern(
            pattern_id=uuid4(),
            type=PatternType.STRUCTURE,
            content=f"Text with {len(lines)} lines",
            abstraction_level=0.4,
            confidence=0.5,
        ))

        return patterns

    def _extract_key_phrases(self, text: str, max_phrases: int = 5) -> list[str]:
        """Extract key phrases from text."""
        import re

        # Simple extraction based on capitalization and length
        words = text.split()
        phrases = []

        current_phrase = []
        for word in words:
            if word and word[0].isupper() and len(word) > 3:
                current_phrase.append(word)
            else:
                if len(current_phrase) >= 2:
                    phrases.append(" ".join(current_phrase))
                    if len(phrases) >= max_phrases:
                        break
                current_phrase = []

        return phrases[:max_phrases]


class DataExtractor(BaseExtractor):
    """Extracts patterns from data extraction output."""

    async def extract(self, output: Any, task_type: str) -> list[FragmentPattern]:
        """Extract data patterns from output."""
        if not isinstance(output, dict):
            return []

        patterns = []

        # Extract schema
        if "schema" in output:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type=PatternType.STRUCTURE,
                content=str(output["schema"]),
                abstraction_level=0.8,
                confidence=0.9,
            ))

        # Extract field patterns
        if "fields" in output:
            for field in output["fields"]:
                patterns.append(FragmentPattern(
                    pattern_id=uuid4(),
                    type=PatternType.TEMPLATE,
                    content=f"Field: {field.get('name', 'unknown')}",
                    abstraction_level=0.7,
                    confidence=0.8,
                ))

        return patterns


# Factory function
def get_extractor_for_task_type(task_type: str) -> BaseExtractor:
    """Get appropriate extractor for task type."""
    extractors = {
        "code_generation": CodeExtractor(),
        "text_summarization": TextExtractor(),
        "data_extraction": DataExtractor(),
        "classification": TextExtractor(),
        "translation": TextExtractor(),
        "question_answering": TextExtractor(),
    }

    return extractors.get(task_type, TextExtractor())
