"""Embedding service for semantic similarity."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx
import numpy as np
import hashlib

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.exceptions import EmbeddingError


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        pass


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-ada-002",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ):
        self.api_key = api_key or get_settings().llm_api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._dimension: int | None = None

        # Model dimensions
        self._model_dimensions = {
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }

    def get_dimension(self) -> int:
        """Get embedding dimension for current model."""
        if self._dimension is None:
            self._dimension = self._model_dimensions.get(self.model, 1536)
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "input": texts,
            "model": self.model,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                embeddings = [
                    item["embedding"] for item in data["data"]
                ]
                return embeddings

            except httpx.HTTPStatusError as e:
                raise EmbeddingError(
                    f"OpenAI API error: {e.response.status_code}",
                    model=self.model,
                ) from e
            except httpx.RequestError as e:
                raise EmbeddingError(
                    f"Request failed: {str(e)}",
                    model=self.model,
                ) from e


class LocalEmbedder(EmbeddingProvider):
    """
    Local embedding provider using sentence-transformers.

    Useful for development/testing without API costs.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._dimension: int | None = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                raise EmbeddingError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

    def get_dimension(self) -> int:
        """Get embedding dimension."""
        self._load_model()
        return self._dimension or 384

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        self._load_model()

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            self._model.encode,
            texts,
        )

        return embeddings.tolist()


class HashEmbedder(EmbeddingProvider):
    def __init__(self, dimension: int | None = None):
        settings = get_settings()
        self._dimension = dimension or settings.embedding_dim

    def get_dimension(self) -> int:
        return self._dimension

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        dim = self._dimension
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            seed = int.from_bytes(digest[:8], "big", signed=False)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(dim, dtype=np.float32)
            norm = float(np.linalg.norm(v)) or 1.0
            vectors.append((v / norm).tolist())
        return vectors


class EmbeddingService:
    """
    High-level embedding service with caching.

    Provides a unified interface for text embedding operations
    with built-in batching and caching.
    """

    def __init__(self, provider: EmbeddingProvider | None = None):
        if provider is not None:
            self.provider = provider
        else:
            settings = get_settings()
            self.provider = OpenAIEmbedder() if settings.llm_api_key else HashEmbedder()
        self._cache: dict[str, list[float]] = {}
        self._cache_max_size = 10000

    async def embed(
        self,
        text: str,
        use_cache: bool = True,
    ) -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            Embedding vector
        """
        # Check cache
        if use_cache and text in self._cache:
            return self._cache[text]

        # Generate embedding
        embedding = await self.provider.embed(text)

        # Cache result
        if use_cache and len(self._cache) < self._cache_max_size:
            self._cache[text] = embedding

        return embedding

    async def embed_context(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> list[float]:
        """
        Embed combined prompt and context.

        Creates a unified embedding that captures both the task
        and the context in a single vector.
        """
        import json

        # Combine prompt and context
        combined = prompt
        if context:
            context_str = json.dumps(context, sort_keys=True, default=str)
            combined = f"{prompt}\n\nContext: {context_str}"

        return await self.embed(combined)

    async def embed_batch(
        self,
        texts: list[str],
        use_cache: bool = True,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Uses caching for already-embedded texts.
        """
        if not texts:
            return []

        # Filter cached and uncached texts
        cached = []
        uncached = []
        uncached_indices = []

        for i, text in enumerate(texts):
            if use_cache and text in self._cache:
                cached.append((i, self._cache[text]))
            else:
                uncached.append(text)
                uncached_indices.append(i)

        # Generate embeddings for uncached
        if uncached:
            new_embeddings = await self.provider.embed_batch(uncached)

            # Cache new embeddings
            if use_cache and len(self._cache) < self._cache_max_size:
                for text, embedding in zip(uncached, new_embeddings):
                    self._cache[text] = embedding

        # Combine results
        results = [None] * len(texts)
        for i, embedding in cached:
            results[i] = embedding
        for idx, embedding in zip(uncached_indices, new_embeddings):
            results[idx] = embedding

        return results  # type: ignore

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self.provider.get_dimension()
