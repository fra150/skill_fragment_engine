"""Vector store using FAISS for semantic search."""

from __future__ import annotations

import json
import os
import threading
import time
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
        
        # Simple block-level cache for recently accessed vectors to reduce disk I/O
        self._vector_cache: dict[str, np.ndarray] = {}
        self._cache_size_limit = 1000  # Maximum number of vectors to cache
        self._cache_hits = 0
        self._cache_misses = 0

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

                logger.info("vector_store_loaded", size=self.index.ntotal if self.index else 0)

            except Exception as e:
                logger.warning("vector_store_load_failed", error=str(e))
                self._create_index()

        else:
            self._create_index()

    def _create_index(self) -> None:
        """Create a new FAISS index, optionally using IVF-PQ for better scalability."""
        settings = get_settings()
        
        # Check if IVF-PQ is enabled
        if getattr(settings, 'vector_use_ivf_pq', False):
            self._create_ivf_pq_index(settings)
        else:
            # Fall back to original flat index
            if self.metric == "cosine":
                # For cosine similarity, use Inner Product with normalized vectors
                self.index = faiss.IndexFlatIP(self.dimension)
            elif self.metric == "l2":
                self.index = faiss.IndexFlatL2(self.dimension)
            else:
                self.index = faiss.IndexFlatIP(self.dimension)

        self.id_map = {}
        self.reverse_map = {}

        logger.info("vector_store_created", 
                   dimension=self.dimension, 
                   metric=self.metric, 
                   index_type=type(self.index).__name__,
                   use_ivf_pq=getattr(settings, 'vector_use_ivf_pq', False))

    def _create_ivf_pq_index(self, settings) -> None:
        """Create a new FAISS IVF-PQ/OPQ index for better scalability with large datasets."""
        # IVF parameters from settings
        nlist = getattr(settings, 'vector_ivf_nlist', 100)
        # Ensure nlist is at least 1 and reasonable
        nlist = max(1, min(nlist, 10000))
        
        # PQ parameters from settings
        m = getattr(settings, 'vector_pq_m', 16)
        nbits = getattr(settings, 'vector_pq_nbits', 8)
        
        # OPQ parameters from settings
        use_opq = getattr(settings, 'vector_use_opq', False)
        opq_train_iterations = getattr(settings, 'vector_opq_train_iterations', 20)
        
        # Ensure m divides dimension evenly for PQ
        if self.dimension % m != 0:
            # Adjust m to divide dimension evenly
            for candidate_m in range(min(m, self.dimension), 0, -1):
                if self.dimension % candidate_m == 0:
                    m = candidate_m
                    break
            # If no divisor found, use 1 (no compression)
            if m == 0:
                m = 1
        
        # Create quantizer (coarse quantizer)
        if self.metric == "cosine":
            quantizer = faiss.IndexFlatIP(self.dimension)
        else:
            quantizer = faiss.IndexFlatL2(self.dimension)
        
        # Create base IVF-PQ index
        ivf_pq_index = faiss.IndexIVFPQ(quantizer, self.dimension, nlist, m, nbits)
        
        # Wrap with OPQ if enabled
        if use_opq:
            self.index = faiss.IndexOPQ(ivf_pq_index, m, opq_train_iterations)
        else:
            self.index = ivf_pq_index
        
        # Mark as not trained - we'll train when adding vectors
        self.index.is_trained = False
        
        self.id_map = {}
        self.reverse_map = {}
        
        logger.info("vector_store_created_ivfopq" if use_opq else "vector_store_created_ivfpq", 
                   dimension=self.dimension, 
                   metric=self.metric, 
                   nlist=nlist, 
                   m=m, 
                   nbits=nbits,
                   use_opq=use_opq)

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

        embedding_np = np.array(embedding, dtype=np.float32)

        # Normalize for cosine similarity
        if self.metric == "cosine":
            norm = np.linalg.norm(embedding_np)
            if norm > 0:
                embedding_np = embedding_np / norm
        
        # Handle replacement
        if fragment_id in self.reverse_map:
            if replace:
                # For simplicity, we'll remove and re-add
                self._remove_from_index(fragment_id)
            else:
                logger.warning("fragment_already_exists", fragment_id=fragment_id)
                return

        # For IVF-PQ indexes, we need to train before adding if not already trained
        if (hasattr(self.index, 'is_trained') and not self.index.is_trained and 
            self.index.ntotal >= 100):  # Train when we have enough vectors
            # Collect training vectors
            train_vectors = []
            train_ids = []
            for i in range(min(1000, self.index.ntotal)):  # Use up to 1000 vectors for training
                if i in self.id_map:
                    vec = self.index.reconstruct(i)
                    train_vectors.append(vec)
                    train_ids.append(i)
            
            if train_vectors:
                train_data = np.array(train_vectors, dtype=np.float32)
                train_ids_array = np.array(train_ids, dtype=np.int64)
                self.index.train(train_data)
                self.index.add(train_data)
                self.index.is_trained = True
                logger.info("vector_store_index_trained_during_add", 
                           vectors_trained=len(train_vectors))

        # Add to index
        position = self.index.ntotal
        embedding_to_add = np.array(embedding, dtype=np.float32).reshape(1, -1)
        self.index.add(embedding_to_add)

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

        query_np = np.array(query_embedding, dtype=np.float32).reshape(1, -1)

        # Normalize query for cosine similarity
        if self.metric == "cosine":
            norm = np.linalg.norm(query_np)
            if norm > 0:
                query_np = query_np / norm
        
        # Use the numpy array for search
        query = query_np

        # Search
        k = min(top_k * 2, self.index.ntotal)  # Get extra for filtering
        if k == 0:
            return []
        
        # Set nprobe for IVF indexes to control search accuracy/speed tradeoff
        if hasattr(self.index, 'nprobe'):
            from skill_fragment_engine.core.config import get_settings
            settings = get_settings()
            self.index.nprobe = getattr(settings, 'vector_nprobe', 10)

        # For IVF indexes, we need to train if not already trained
        if hasattr(self.index, 'is_trained') and not self.index.is_trained and self.index.ntotal > 0:
            # Train with existing vectors
            embeddings_to_train = []
            for i in range(min(1000, self.index.ntotal)):  # Train with up to 1000 vectors
                if i in self.id_map:
                    embeddings_to_train.append(self.index.reconstruct(i))
            if embeddings_to_train:
                train_data = np.array(embeddings_to_train, dtype=np.float32)
                self.index.train(train_data)
                self.index.is_trained = True
                logger.info("vector_store_index_trained", vectors_trained=len(embeddings_to_train))
        
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
        """Get embedding for a fragment with caching to reduce disk I/O."""
        if self.index is None or fragment_id not in self.reverse_map:
            return None

        # Check cache first
        if fragment_id in self._vector_cache:
            self._cache_hits += 1
            return self._vector_cache[fragment_id].tolist()
        
        self._cache_misses += 1
        
        # If not in cache, get from index
        position = self.reverse_map[fragment_id]
        embedding = self.index.reconstruct(position)
        embedding_np = np.array(embedding, dtype=np.float32)
        
        # Add to cache, removing oldest if at limit
        if len(self._vector_cache) >= self._cache_size_limit:
            # Remove oldest item (simple FIFO)
            oldest_key = next(iter(self._vector_cache))
            del self._vector_cache[oldest_key]
        
        self._vector_cache[fragment_id] = embedding_np
        return embedding_np.tolist()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache hit/miss statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._vector_cache),
            "cache_limit": self._cache_size_limit
        }

    @property
    def index_utilization(self) -> dict[str, Any]:
        """Get index utilization metrics."""
        if self.index is None:
            return {"status": "not_initialized"}
        
        # Basic metrics for all index types
        utilization = {
            "total_vectors": self.index.ntotal,
            "is_trained": getattr(self.index, 'is_trained', False),
            "index_type": type(self.index).__name__
        }
        
        # Safely add IVF-specific metrics if available
        nlist = getattr(self.index, 'nlist', None)
        if nlist is not None:
            utilization["nlist"] = nlist
        
        # Safely add PQ-specific metrics if available
        pq = getattr(self.index, 'pq', None)
        if pq is not None:
            utilization["pq_m"] = getattr(pq, 'M', None)
            utilization["pq_nbits"] = getattr(pq, 'ksub', None)
                
        return utilization

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
