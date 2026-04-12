"""Clustering algorithms for fragment grouping."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ClusterResult:
    """Result of clustering operation."""
    cluster_id: int
    fragment_ids: list[str]
    centroid: np.ndarray | None = None
    size: int = 0


class ClusteringAlgorithm(ABC):
    """Abstract base class for clustering algorithms."""

    @abstractmethod
    def fit_predict(self, embeddings: np.ndarray, fragment_ids: list[str]) -> list[int]:
        """Fit and predict cluster labels."""
        pass

    @abstractmethod
    def fit(self, embeddings: np.ndarray) -> None:
        """Fit the algorithm to embeddings."""
        pass

    @abstractmethod
    def predict(self, embeddings: np.ndarray) -> list[int]:
        """Predict cluster labels for embeddings."""
        pass


class KMeansClustering(ClusteringAlgorithm):
    """K-Means clustering implementation."""

    def __init__(self, n_clusters: int = 10, max_iter: int = 300, random_state: int = 42):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = random_state
        self.centroids: np.ndarray | None = None

    def fit_predict(self, embeddings: np.ndarray, fragment_ids: list[str]) -> list[int]:
        self.fit(embeddings)
        return self.predict(embeddings)

    def fit(self, embeddings: np.ndarray) -> None:
        """Fit K-Means to embeddings."""
        np.random.seed(self.random_state)
        n_samples = embeddings.shape[0]
        
        if self.n_clusters > n_samples:
            self.n_clusters = max(1, n_samples)
        
        indices = np.random.choice(n_samples, self.n_clusters, replace=False)
        self.centroids = embeddings[indices].copy()

        for _ in range(self.max_iter):
            distances = np.linalg.norm(embeddings[:, np.newaxis] - self.centroids, axis=2)
            labels = np.argmin(distances, axis=1)

            new_centroids = np.zeros_like(self.centroids)
            for k in range(self.n_clusters):
                mask = labels == k
                if mask.sum() > 0:
                    new_centroids[k] = embeddings[mask].mean(axis=0)
                else:
                    new_centroids[k] = self.centroids[k]

            if np.allclose(self.centroids, new_centroids):
                break
            self.centroids = new_centroids

        logger.info("kmeans_fitted", n_clusters=self.n_clusters, samples=n_samples)

    def predict(self, embeddings: np.ndarray) -> list[int]:
        """Predict cluster labels."""
        if self.centroids is None:
            raise ValueError("Model not fitted yet")
        
        distances = np.linalg.norm(embeddings[:, np.newaxis] - self.centroids, axis=2)
        return np.argmin(distances, axis=1).tolist()

    def get_centroids(self) -> np.ndarray | None:
        """Get cluster centroids."""
        return self.centroids


class DBSCANClustering(ClusteringAlgorithm):
    """DBSCAN density-based clustering."""

    def __init__(self, eps: float = 0.5, min_samples: int = 5):
        self.eps = eps
        self.min_samples = min_samples
        self.labels: np.ndarray | None = None

    def fit_predict(self, embeddings: np.ndarray, fragment_ids: list[str]) -> list[int]:
        self.fit(embeddings)
        return self.predict(embeddings)

    def fit(self, embeddings: np.ndarray) -> None:
        """Fit DBSCAN to embeddings."""
        n_samples = embeddings.shape[0]
        self.labels = np.full(n_samples, -1)
        cluster_id = 0

        for i in range(n_samples):
            if self.labels[i] != -1:
                continue

            neighbors = self._get_neighbors(embeddings, i)
            if len(neighbors) < self.min_samples:
                continue

            self._expand_cluster(embeddings, i, neighbors, cluster_id)
            cluster_id += 1

        n_clusters = len(set(self.labels)) - (1 if -1 in self.labels else 0)
        logger.info("dbscan_fitted", n_clusters=n_clusters, noise_points=np.sum(self.labels == -1))

    def _get_neighbors(self, embeddings: np.ndarray, idx: int) -> list[int]:
        """Find neighbors within eps distance."""
        distances = np.linalg.norm(embeddings - embeddings[idx], axis=1)
        return np.where(distances <= self.eps)[0].tolist()

    def _expand_cluster(self, embeddings: np.ndarray, idx: int, neighbors: list[int], cluster_id: int) -> None:
        """Expand cluster from seed point."""
        self.labels[idx] = cluster_id
        i = 0
        while i < len(neighbors):
            neighbor = neighbors[i]
            if self.labels[neighbor] == -1:
                self.labels[neighbor] = cluster_id
                new_neighbors = self._get_neighbors(embeddings, neighbor)
                if len(new_neighbors) >= self.min_samples:
                    neighbors.extend(new_neighbors)
            i += 1

    def predict(self, embeddings: np.ndarray) -> list[int]:
        """Predict cluster labels."""
        if self.labels is None:
            raise ValueError("Model not fitted yet")
        return self.labels.tolist()


class HierarchicalClustering(ClusteringAlgorithm):
    """Agglomerative hierarchical clustering."""

    def __init__(self, n_clusters: int = 10, linkage: str = "average"):
        self.n_clusters = n_clusters
        self.linkage = linkage
        self.labels: np.ndarray | None = None

    def fit_predict(self, embeddings: np.ndarray, fragment_ids: list[str]) -> list[int]:
        self.fit(embeddings)
        return self.predict(embeddings)

    def fit(self, embeddings: np.ndarray) -> None:
        """Fit hierarchical clustering."""
        n_samples = embeddings.shape[0]
        
        if self.n_clusters > n_samples:
            self.n_clusters = max(1, n_samples)

        distances = self._compute_distances(embeddings)
        clusters = list(range(n_samples))
        cluster_centroids = {i: embeddings[i].copy() for i in range(n_samples)}

        while len(clusters) > self.n_clusters:
            min_dist = float('inf')
            merge = (0, 1)

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    c1, c2 = clusters[i], clusters[j]
                    dist = self._cluster_distance(cluster_centroids[c1], cluster_centroids[c2], distances, embeddings)
                    if dist < min_dist:
                        min_dist = dist
                        merge = (c1, c2)

            c1, c2 = merge
            new_centroid = (cluster_centroids[c1] + cluster_centroids[c2]) / 2
            new_id = min(c1, c2)
            
            clusters.remove(c1)
            clusters.remove(c2)
            clusters.append(new_id + n_samples)
            cluster_centroids[new_id + n_samples] = new_centroid
            cluster_centroids.pop(c1, None)
            cluster_centroids.pop(c2, None)

        self.labels = np.zeros(n_samples, dtype=int)
        for new_id in clusters:
            orig_id = new_id % n_samples
            self.labels[orig_id] = clusters.index(new_id)

        logger.info("hierarchical_fitted", n_clusters=self.n_clusters, samples=n_samples)

    def _compute_distances(self, embeddings: np.ndarray) -> np.ndarray:
        """Compute pairwise distances."""
        n = embeddings.shape[0]
        distances = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(embeddings[i] - embeddings[j])
                distances[i, j] = distances[j, i] = d
        return distances

    def _cluster_distance(self, c1: np.ndarray, c2: np.ndarray, distances: np.ndarray, embeddings: np.ndarray) -> float:
        """Compute distance between clusters."""
        return float(np.linalg.norm(c1 - c2))

    def predict(self, embeddings: np.ndarray) -> list[int]:
        """Predict cluster labels."""
        if self.labels is None:
            raise ValueError("Model not fitted yet")
        return self.labels.tolist()


class AutoClustering:
    """Automatic clustering with adaptive cluster count."""

    def __init__(
        self,
        method: str = "kmeans",
        min_clusters: int = 2,
        max_clusters: int = 50,
    ):
        self.method = method
        self.min_clusters = min_clusters
        self.max_clusters = max_clusters
        self._algorithm: ClusteringAlgorithm | None = None

    def fit_predict(self, embeddings: np.ndarray, fragment_ids: list[str]) -> list[int]:
        """Automatically determine optimal clusters and fit."""
        n_samples = embeddings.shape[0]
        
        if n_samples < self.min_clusters:
            logger.warning("not_enough_samples_for_clustering", n_samples=n_samples)
            return [0] * n_samples

        n_clusters = self._determine_optimal_clusters(embeddings, n_samples)
        
        if self.method == "kmeans":
            self._algorithm = KMeansClustering(n_clusters=n_clusters)
        elif self.method == "dbscan":
            self._algorithm = DBSCANClustering(eps=0.5, min_samples=min(5, n_samples // 10))
        elif self.method == "hierarchical":
            self._algorithm = HierarchicalClustering(n_clusters=n_clusters)
        else:
            self._algorithm = KMeansClustering(n_clusters=n_clusters)

        labels = self._algorithm.fit_predict(embeddings, fragment_ids)
        
        n_unique = len(set(labels))
        logger.info("auto_clustering_complete", 
                   method=self.method, 
                   n_clusters=n_unique,
                   n_samples=n_samples)
        
        return labels

    def _determine_optimal_clusters(self, embeddings: np.ndarray, n_samples: int) -> int:
        """Determine optimal number of clusters using elbow method."""
        if n_samples < 10:
            return min(n_samples, self.max_clusters)
        
        max_k = min(self.max_clusters, n_samples)
        inertias = []
        
        for k in range(2, max_k + 1):
            kmeans = KMeansClustering(n_clusters=k, max_iter=100)
            kmeans.fit(embeddings)
            
            if kmeans.centroids is not None:
                distances = np.linalg.norm(embeddings[:, np.newaxis] - kmeans.centroids, axis=2)
                labels = np.argmin(distances, axis=1)
                inertia = sum(
                    np.linalg.norm(embeddings[i] - kmeans.centroids[labels[i]]) 
                    for i in range(n_samples)
                )
                inertias.append(inertia)

        if len(inertias) < 2:
            return max(2, n_samples // 10)

        deltas = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
        elbow_idx = 0
        max_delta = 0
        for i, delta in enumerate(deltas):
            if delta > max_delta:
                max_delta = delta
                elbow_idx = i
        
        return min(max(2, elbow_idx + 2), self.max_clusters)

    def get_cluster_results(self, embeddings: np.ndarray, fragment_ids: list[str]) -> list[ClusterResult]:
        """Get cluster results with fragment assignments."""
        if self._algorithm is None:
            return []
        
        labels = self._algorithm.predict(embeddings)
        
        cluster_map: dict[int, list[str]] = {}
        centroids = getattr(self._algorithm, 'centroids', None)
        
        for i, (fragment_id, label) in enumerate(zip(fragment_ids, labels)):
            if label not in cluster_map:
                cluster_map[label] = []
            cluster_map[label].append(fragment_id)
        
        results = []
        for cluster_id, fids in cluster_map.items():
            centroid = None
            if centroids is not None and cluster_id < len(centroids):
                centroid = centroids[cluster_id]
            
            results.append(ClusterResult(
                cluster_id=cluster_id,
                fragment_ids=fids,
                centroid=centroid,
                size=len(fids)
            ))
        
        return results


class ClusteringService:
    """Service for managing cluster operations."""

    def __init__(self, method: str = "auto"):
        self.method = method
        self._clustering: AutoClustering | None = None

    def cluster_fragments(
        self,
        embeddings: dict[str, list[float]],
        method: str | None = None,
    ) -> dict[str, int]:
        """
        Cluster fragments based on embeddings.

        Args:
            embeddings: Dict mapping fragment_id to embedding vector
            method: Clustering method override

        Returns:
            Dict mapping fragment_id to cluster_id
        """
        if not embeddings:
            return {}

        use_method = method or self.method
        fragment_ids = list(embeddings.keys())
        matrix = np.array(list(embeddings.values()), dtype=np.float32)

        if use_method == "auto":
            self._clustering = AutoClustering()
        elif use_method == "kmeans":
            self._clustering = AutoClustering(method="kmeans")
        elif use_method == "dbscan":
            self._clustering = AutoClustering(method="dbscan")
        elif use_method == "hierarchical":
            self._clustering = AutoClustering(method="hierarchical")
        else:
            self._clustering = AutoClustering()

        labels = self._clustering.fit_predict(matrix, fragment_ids)
        
        result = {fid: label for fid, label in zip(fragment_ids, labels)}
        
        logger.info("clustering_completed", 
                   method=use_method, 
                   n_fragments=len(fragment_ids),
                   n_clusters=len(set(labels)))
        
        return result

    def get_cluster_info(self, embeddings: dict[str, list[float]]) -> list[dict[str, Any]]:
        """Get detailed cluster information."""
        if self._clustering is None:
            return []

        fragment_ids = list(embeddings.keys())
        matrix = np.array(list(embeddings.values()), dtype=np.float32)

        results = self._clustering.get_cluster_results(matrix, fragment_ids)
        
        return [
            {
                "cluster_id": r.cluster_id,
                "size": r.size,
                "fragment_ids": r.fragment_ids,
                "centroid": r.centroid.tolist() if r.centroid is not None else None
            }
            for r in results
        ]

    def find_similar_in_cluster(
        self,
        target_fragment_id: str,
        cluster_mapping: dict[str, int],
        embeddings: dict[str, list[float]],
        exclude_target: bool = True
    ) -> list[str]:
        """Find similar fragments within the same cluster."""
        target_cluster = cluster_mapping.get(target_fragment_id)
        if target_cluster is None:
            return []

        similar = [
            fid for fid, cid in cluster_mapping.items()
            if cid == target_cluster and fid != target_fragment_id
        ]
        
        return similar