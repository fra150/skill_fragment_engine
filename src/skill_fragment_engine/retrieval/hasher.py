"""Input hashing utilities."""

import hashlib
import json
from typing import Any


class InputHasher:
    """
    Utility for creating deterministic hashes of inputs.

    Used for exact-match lookups and caching.
    """

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Create SHA-256 hash of prompt."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_context(context: dict[str, Any] | None) -> str:
        """Create SHA-256 hash of context dictionary."""
        if context is None:
            context = {}

        # Normalize by sorting keys and serializing consistently
        normalized = json.dumps(context, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_parameters(parameters: dict[str, Any] | None) -> str:
        """Create SHA-256 hash of parameters dictionary."""
        if parameters is None:
            parameters = {}

        normalized = json.dumps(parameters, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_input(
        prompt: str,
        context: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """
        Create combined hash of all input components.

        Returns a single hash that uniquely identifies this input.
        """
        components = [
            InputHasher.hash_prompt(prompt),
            InputHasher.hash_context(context),
            InputHasher.hash_parameters(parameters),
        ]
        combined = "|".join(components)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_output(output: Any) -> str:
        """Create SHA-256 hash of output."""
        normalized = json.dumps(output, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def are_signatures_equal(
        sig1: dict[str, str],
        sig2: dict[str, str],
    ) -> bool:
        """Check if two signatures are equal."""
        return (
            sig1.get("prompt_hash") == sig2.get("prompt_hash")
            and sig1.get("context_hash") == sig2.get("context_hash")
            and sig1.get("parameters_hash") == sig2.get("parameters_hash")
        )
