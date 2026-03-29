"""Vector store using FAISS for semantic search."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import faiss
import numpy as np
import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.exceptions import RetrievalError

logger = structlog.get_logger(__name__)


class VectorStore:
    """
    FAISS-based vector store for semantic similarity search.

    Stores embeddings and enables fast nearest-neighbor queries.
    """

    def __init__(
        self,
        dimension: int | None = None,
        index_path: str | None = None,
        metric: str = "cosine",
    ):
        settings = get_settings()
        self.dimension = dimension or settings.embedding_dim
        self.index_path = index_path or settings.vector_store_path
        self.metric = metric

        self.index: faiss.Index | None = None
        self.id_map: dict[int, str] = {}  # index position -> fragment_id
        self.reverse_map: dict[str, int] = {}  # fragment_id -> index position

        # Ensure directory exists
        Path(self.index_path).mkdir(parents=True, exist_ok=True)

        self._load_index()

    def _load_index(self) -> None:
        """Load existing index or create new one."""
        index_file = Path(self.index_path) / "index.faiss"
        id_map_file = Path(self.index_path) / "id_map.json"

        if index_file.exists() and id_map_file.exists():
            try:
                self.index = faiss.read_index(str(index_file))

                with open(id_map_file) as f:
                    id_map_data = json.load(f)
                    self.id_map = {int(k): v for k, v in id_map_data["id_map"].items()}
                    self.reverse_map = {v: k for k, v in self.id_map.items()}

                logger.info("vector_store_loaded", size=self.index.ntotal)

            except Exception as e:
                logger.warning("vector_store_load_failed", error=str(e))
                self._create_index()

        else:
            self._create_index()

    def _create_index(self) -> None:
        """Create a new FAISS index."""
        if self.metric == "cosine":
            # For cosine similarity, use Inner Product with normalized vectors
            self.index = faiss.IndexFlatIP(self.dimension)
        elif self.metric == "l2":
            self.index = faiss.IndexFlatL2(self.dimension)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)

        self.id_map = {}
        self.reverse_map = {}

        logger.info("vector_store_created", dimension=self.dimension, metric=self.metric)

    def add(
        self,
        fragment_id: str,
        embedding: list[float],
        replace: bool = True,
    ) -> None:
        """
        Add embedding to the index.

        Args:
            fragment_id: Unique identifier for the fragment
            embedding: Embedding vector
            replace: If True, replace existing embedding for this fragment
        """
        if self.index is None:
            raise RetrievalError("Index not initialized")

        embedding = np.array(embedding, dtype=np.float32)

        # Normalize for cosine similarity
        if self.metric == "cosine":
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

        # Handle replacement
        if fragment_id in self.reverse_map:
            if replace:
                existing_pos = self.reverse_map[fragment_id]
                # Direct replacement at existing position
                self.index.reconstruct(existing_pos)  # Not typically used for update
                # For simplicity, we'll remove and re-add
                self._remove_from_index(fragment_id)
            else:
                logger.warning("fragment_already_exists", fragment_id=fragment_id)
                return

        # Add to index
        position = self.index.ntotal
        self.index.add(embedding.reshape(1, -1))

        # Update maps
        self.id_map[position] = fragment_id
        self.reverse_map[fragment_id] = position

    def _remove_from_index(self, fragment_id: str) -> None:
        """Remove fragment from index (marks as removed)."""
        if fragment_id in self.reverse_map:
            position = self.reverse_map[fragment_id]
            del self.id_map[position]
            del self.reverse_map[fragment_id]

            # FAISS doesn't support efficient removal, so we just update maps
            # The position will remain in the index but won't be referenced

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[str, float]]:
        """
        Search for similar embeddings.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            min_score: Minimum similarity score

        Returns:
            List of (fragment_id, score) tuples
        """
        if self.index is None:
            raise RetrievalError("Index not initialized")

        query = np.array(query_embedding, dtype=np.float32).reshape(1, -1)

        # Normalize query for cosine similarity
        if self.metric == "cosine":
            norm = np.linalg.norm(query)
            if norm > 0:
                query = query / norm

        # Search
        k = min(top_k * 2, self.index.ntotal)  # Get extra for filtering
        if k == 0:
            return []

        scores, indices = self.index.search(query, k)

        # Filter and format results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:  # FAISS returns -1 for invalid indices
                continue

            fragment_id = self.id_map.get(int(idx))
            if fragment_id is None:
                continue

            # Convert distance to similarity if needed
            if self.metric == "cosine":
                similarity = float(score)  # Already similarity for IP with normalized
            else:
                # Convert L2 distance to similarity
                similarity = 1.0 / (1.0 + float(score))

            if similarity >= min_score:
                results.append((fragment_id, similarity))

        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get(self, fragment_id: str) -> list[float] | None:
        """Get embedding for a fragment."""
        if self.index is None or fragment_id not in self.reverse_map:
            return None

        position = self.reverse_map[fragment_id]
        embedding = self.index.reconstruct(position)
        return embedding.tolist()

    def remove(self, fragment_id: str) -> bool:
        """Remove fragment from index."""
        if fragment_id not in self.reverse_map:
            return False

        self._remove_from_index(fragment_id)
        return True

    def save(self) -> None:
        """Save index and ID map to disk."""
        if self.index is None:
            return

        index_file = Path(self.index_path) / "index.faiss"
        id_map_file = Path(self.index_path) / "id_map.json"

        faiss.write_index(self.index, str(index_file))

        with open(id_map_file, "w") as f:
            json.dump({
                "id_map": {str(k): v for k, v in self.id_map.items()},
                "dimension": self.dimension,
                "metric": self.metric,
            }, f)

        logger.info("vector_store_saved", path=self.index_path)

    @property
    def size(self) -> int:
        """Get number of embeddings in index."""
        return len(self.id_map)

    def clear(self) -> None:
        """Clear all embeddings."""
        self._create_index()
