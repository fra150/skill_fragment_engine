"""Similarity algorithms for fragment matching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Set
import math


class SimilarityAlgorithm(ABC):
    """Abstract base class for similarity algorithms."""

    @abstractmethod
    def compute_similarity(self, query_words: Set[str], stored_words: Set[str]) -> float:
        """
        Compute similarity between two sets of words.

        Args:
            query_words: Set of words from the query prompt
            stored_words: Set of words from the stored prompt

        Returns:
            Similarity score between 0.0 and 1.0
        """
        pass


class JaccardSimilarity(SimilarityAlgorithm):
    """Jaccard similarity coefficient."""

    def compute_similarity(self, query_words: Set[str], stored_words: Set[str]) -> float:
        """
        Compute Jaccard similarity: |A ∩ B| / |A ∪ B|

        Args:
            query_words: Set of words from the query prompt
            stored_words: Set of words from the stored prompt

        Returns:
            Jaccard similarity score between 0.0 and 1.0
        """
        if not query_words and not stored_words:
            return 1.0
        if not query_words or not stored_words:
            return 0.0

        intersection = len(query_words & stored_words)
        union = len(query_words | stored_words)
        return intersection / union if union > 0 else 0.0


class CosineSimilarity(SimilarityAlgorithm):
    """Cosine similarity based on word frequency."""

    def compute_similarity(self, query_words: Set[str], stored_words: Set[str]) -> float:
        """
        Compute cosine similarity treating word sets as binary vectors.

        Args:
            query_words: Set of words from the query prompt
            stored_words: Set of words from the stored prompt

        Returns:
            Cosine similarity score between 0.0 and 1.0
        """
        if not query_words and not stored_words:
            return 1.0
        if not query_words or not stored_words:
            return 0.0

        intersection = len(query_words & stored_words)
        query_norm = math.sqrt(len(query_words))
        stored_norm = math.sqrt(len(stored_words))
        
        if query_norm == 0 or stored_norm == 0:
            return 0.0
            
        return intersection / (query_norm * stored_norm)


class DiceSimilarity(SimilarityAlgorithm):
    """Dice similarity coefficient."""

    def compute_similarity(self, query_words: Set[str], stored_words: Set[str]) -> float:
        """
        Compute Dice similarity: 2 * |A ∩ B| / (|A| + |B|)

        Args:
            query_words: Set of words from the query prompt
            stored_words: Set of words from the stored prompt

        Returns:
            Dice similarity score between 0.0 and 1.0
        """
        if not query_words and not stored_words:
            return 1.0
        if not query_words or not stored_words:
            return 0.0

        intersection = len(query_words & stored_words)
        total = len(query_words) + len(stored_words)
        return (2.0 * intersection) / total if total > 0 else 0.0


# Factory for creating similarity algorithms
class SimilarityFactory:
    """Factory for creating similarity algorithm instances."""

    _algorithms = {
        "jaccard": JaccardSimilarity,
        "cosine": CosineSimilarity,
        "dice": DiceSimilarity,
    }

    @classmethod
    def create(cls, algorithm_name: str) -> SimilarityAlgorithm:
        """
        Create a similarity algorithm instance.

        Args:
            algorithm_name: Name of the algorithm ("jaccard", "cosine", "dice")

        Returns:
            SimilarityAlgorithm instance

        Raises:
            ValueError: If algorithm_name is not supported
        """
        algorithm_class = cls._algorithms.get(algorithm_name.lower())
        if not algorithm_class:
            raise ValueError(f"Unsupported similarity algorithm: {algorithm_name}")
        return algorithm_class()

    @classmethod
    def get_available_algorithms(cls) -> List[str]:
        """Get list of available algorithm names."""
        return list(cls._algorithms.keys())