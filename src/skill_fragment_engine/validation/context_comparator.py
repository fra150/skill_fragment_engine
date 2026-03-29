"""Context comparison for determining fragment similarity."""

from __future__ import annotations

from typing import Any

import numpy as np

from skill_fragment_engine.core.config import TaskTypeThresholds


class ContextComparator:
    """
    Compares input contexts to determine semantic distance.

    Used by the Validator Engine to decide if a fragment
    can be reused for a new input.
    """

    # Weights for different context components
    PROMPT_WEIGHT = 0.40
    CONTEXT_WEIGHT = 0.35
    PARAMETERS_WEIGHT = 0.25

    def __init__(
        self,
        prompt_weight: float = PROMPT_WEIGHT,
        context_weight: float = CONTEXT_WEIGHT,
        parameters_weight: float = PARAMETERS_WEIGHT,
    ):
        self.prompt_weight = prompt_weight
        self.context_weight = context_weight
        self.parameters_weight = parameters_weight

    def compute_distance(
        self,
        input_a: dict[str, Any],
        input_b: dict[str, Any],
    ) -> float:
        """
        Compute overall distance between two inputs.

        Args:
            input_a: First input (dict with prompt, context, parameters)
            input_b: Second input

        Returns:
            Distance score (0.0 = identical, 1.0 = completely different)
        """
        prompt_distance = self._compare_prompts(
            input_a.get("prompt", ""),
            input_b.get("prompt", ""),
        )

        context_distance = self._compare_contexts(
            input_a.get("context", {}),
            input_b.get("context", {}),
        )

        parameters_distance = self._compare_parameters(
            input_a.get("parameters", {}),
            input_b.get("parameters", {}),
        )

        # Weighted combination
        distance = (
            self.prompt_weight * prompt_distance
            + self.context_weight * context_distance
            + self.parameters_weight * parameters_distance
        )

        return round(distance, 4)

    def _compare_prompts(self, prompt_a: str, prompt_b: str) -> float:
        """
        Compare two prompts using character-level similarity.

        For production, this should use embedding-based comparison.
        """
        if not prompt_a or not prompt_b:
            return 1.0 if prompt_a != prompt_b else 0.0

        # Simple character-level Jaccard similarity as fallback
        set_a = set(prompt_a.lower().split())
        set_b = set(prompt_b.lower().split())

        if not set_a or not set_b:
            return 1.0

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        similarity = intersection / union if union > 0 else 0.0
        return 1.0 - similarity

    def _compare_contexts(
        self,
        context_a: dict[str, Any],
        context_b: dict[str, Any],
    ) -> float:
        """
        Compare two context dictionaries.

        Uses structural comparison with value similarity for primitives.
        """
        if not context_a and not context_b:
            return 0.0

        if not context_a or not context_b:
            return 1.0

        all_keys = set(context_a.keys()) | set(context_b.keys())

        if not all_keys:
            return 0.0

        distances = []
        for key in all_keys:
            val_a = context_a.get(key)
            val_b = context_b.get(key)

            if val_a is None and val_b is None:
                continue

            if val_a is None or val_b is None:
                distances.append(1.0)
                continue

            distances.append(self._value_distance(val_a, val_b))

        return sum(distances) / len(distances) if distances else 0.0

    def _compare_parameters(
        self,
        params_a: dict[str, Any],
        params_b: dict[str, Any],
    ) -> float:
        """
        Compare parameters using Jaccard on keys and value similarity.
        """
        keys_a = set(params_a.keys())
        keys_b = set(params_b.keys())

        if not keys_a and not keys_b:
            return 0.0

        # Key Jaccard distance
        all_keys = keys_a | keys_b
        if not all_keys:
            return 0.0

        key_similarity = len(keys_a & keys_b) / len(all_keys)
        key_distance = 1.0 - key_similarity

        # Value similarity for common keys
        common_keys = keys_a & keys_b
        if not common_keys:
            return key_distance

        value_distances = []
        for key in common_keys:
            value_distances.append(self._value_distance(params_a[key], params_b[key]))

        value_distance = sum(value_distances) / len(value_distances)

        # Combine key and value distances
        return (key_distance + value_distance) / 2

    def _value_distance(self, val_a: Any, val_b: Any) -> float:
        """
        Compute distance between two values.

        Handles different types appropriately.
        """
        # Type mismatch
        if type(val_a) != type(val_b):
            # Special case: int/float comparison
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                max_val = max(abs(val_a), abs(val_b), 1)
                return min(1.0, abs(val_a - val_b) / max_val)
            return 1.0

        # Same type comparison
        if isinstance(val_a, str):
            # String similarity
            if val_a == val_b:
                return 0.0
            # Simple edit distance approximation
            max_len = max(len(val_a), len(val_b), 1)
            common = sum(1 for a, b in zip(val_a, val_b) if a == b)
            return 1.0 - (common / max_len)

        elif isinstance(val_a, (int, float)):
            # Numeric similarity
            max_val = max(abs(val_a), abs(val_b), 1)
            return min(1.0, abs(val_a - val_b) / max_val)

        elif isinstance(val_a, dict):
            # Dict comparison
            return self._compare_contexts(val_a, val_b)

        elif isinstance(val_a, (list, tuple)):
            # List comparison
            return self._list_distance(list(val_a), list(val_b))

        else:
            # Fallback: check equality
            return 0.0 if val_a == val_b else 1.0

    def _list_distance(self, list_a: list, list_b: list) -> float:
        """Compute distance between two lists."""
        if not list_a and not list_b:
            return 0.0
        if not list_a or not list_b:
            return 1.0

        # Simple element-wise comparison
        max_len = max(len(list_a), len(list_b))
        matches = sum(
            self._value_distance(a, b)
            for a, b in zip(list_a, list_b)
        )
        return matches / max_len


def compute_embedding_distance(
    embedding_a: list[float],
    embedding_b: list[float],
) -> float:
    """
    Compute cosine distance between two embeddings.

    Args:
        embedding_a: First embedding vector
        embedding_b: Second embedding vector

    Returns:
        Cosine distance (0.0 = identical, 1.0 = opposite)
    """
    vec_a = np.array(embedding_a, dtype=np.float32)
    vec_b = np.array(embedding_b, dtype=np.float32)

    # Normalize
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 1.0

    vec_a = vec_a / norm_a
    vec_b = vec_b / norm_b

    # Cosine similarity
    similarity = np.dot(vec_a, vec_b)

    # Convert to distance
    similarity = float(max(0.0, min(1.0, similarity)))
    return 1.0 - similarity
