"""Skill Matcher Layer - combines exact and semantic search."""

from __future__ import annotations

from typing import Any, Set

import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.exceptions import RetrievalError
from skill_fragment_engine.core.models import MatchCandidate
from skill_fragment_engine.retrieval.embedder import EmbeddingService
from skill_fragment_engine.retrieval.hasher import InputHasher
from skill_fragment_engine.retrieval.similarity import SimilarityFactory
from skill_fragment_engine.retrieval.vector_store import VectorStore
from skill_fragment_engine.store import FragmentStore

logger = structlog.get_logger(__name__)


class SkillMatcherLayer:
    """
    Combines exact and semantic search for fragment retrieval.

    This is the first layer in the SFE pipeline. It finds potential
    matching fragments for a given input.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        store: FragmentStore | None = None,
        top_k: int | None = None,
        min_similarity: float | None = None,
    ):
        settings = get_settings()

        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()
        self.store = store or FragmentStore()
        self.hasher = InputHasher()
        self.similarity_algorithm = SimilarityFactory.create(
            get_settings().similarity_algorithm or "jaccard"
        )

        self.top_k = top_k or settings.similarity_top_k
        self.min_similarity = min_similarity or settings.min_similarity_score

    async def find_candidates(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
        task_type: str | None = None,
        top_k: int | None = None,
    ) -> list[MatchCandidate]:
        """
        Find potential matching fragments.

        Combines:
        1. Exact match by hash (if available from storage)
        2. Semantic similarity search

        Args:
            prompt: Input prompt
            context: Input context
            parameters: Input parameters
            task_type: Task type filter
            top_k: Override default top_k

        Returns:
            List of match candidates sorted by score
        """
        k = top_k or self.top_k
        candidates: list[MatchCandidate] = []

        exact_match: MatchCandidate | None = None
        if task_type:
            stored = self.store.lookup_exact(
                task_type=task_type,
                prompt=prompt,
                context=context,
                parameters=parameters,
            )
            if stored:
                exact_match = MatchCandidate(
                    fragment_id=str(stored.fragment.fragment_id),
                    score=1.0,
                    match_type="exact",
                )
                candidates.append(exact_match)
                logger.debug("exact_match_found", fragment_id=exact_match.fragment_id)

            for fragment_id, overlap in self.store.lookup_similar(
                task_type=task_type,
                prompt=prompt,
                top_k=k,
            ):
                if exact_match and fragment_id == exact_match.fragment_id:
                    continue
                candidates.append(
                    MatchCandidate(
                        fragment_id=fragment_id,
                        score=overlap,
                        match_type="keyword",
                    )
                )

        settings = get_settings()
        if settings.llm_api_key:
            semantic_candidates = await self._semantic_search(
                prompt=prompt,
                context=context,
                k=max(0, k - (1 if exact_match else 0)),
                task_type=task_type,
            )
            candidates.extend(semantic_candidates)
        else:
            semantic_candidates = []

        # 3. Sort by score
        candidates.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            "candidates_found",
            total=len(candidates),
            exact=1 if exact_match else 0,
            semantic=len(semantic_candidates),
        )

        return candidates[:k]

    async def _semantic_search(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        k: int = 10,
        task_type: str | None = None,
    ) -> list[MatchCandidate]:
        """
        Perform semantic similarity search.

        Returns candidates ranked by semantic similarity.
        """
        # Generate embedding
        embedding = await self.embedding_service.embed_context(prompt, context)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=embedding,
            top_k=k,
            min_score=self.min_similarity,
        )

        candidates = [
            MatchCandidate(
                fragment_id=fragment_id,
                score=score,
                match_type="semantic",
            )
            for fragment_id, score in results
        ]

        return candidates

    def index_fragment(
        self,
        fragment_id: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        """
        Add fragment to the search index.

        Args:
            fragment_id: Unique fragment identifier
            prompt: Fragment prompt
            context: Fragment context
            embedding: Pre-computed embedding (will compute if not provided)
        """
        if embedding is None:
            import asyncio
            # This is synchronous for indexing - use sync wrapper
            embedding = asyncio.get_event_loop().run_until_complete(
                self.embedding_service.embed_context(prompt, context)
            )

        self.vector_store.add(fragment_id, embedding)

    def remove_fragment(self, fragment_id: str) -> None:
        """Remove fragment from search index."""
        self.vector_store.remove(fragment_id)

    async def compute_embedding(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> list[float]:
        """Compute embedding for input."""
        return await self.embedding_service.embed_context(prompt, context)

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return self.embedding_service.dimension
