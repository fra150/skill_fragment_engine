# Automatic Clustering - Skill Fragment Engine

## Overview

The automatic clustering module groups similar fragments into homogeneous clusters, improving the organization and retrieval of stored fragments.

## Available Algorithms

### K-Means
A partition-based clustering algorithm that divides fragments into K clusters according to the Euclidean distance from their centroids.

**Parameters:**
- `n_clusters`: Number of clusters (default: 10)  
- `max_iter`: Maximum iterations (default: 300)  
- `random_state`: Seed for reproducibility  

### DBSCAN (Density-Based)
A density-based clustering algorithm that identifies clusters of arbitrary shape and detects outliers.

**Parameters:**
- `eps`: Neighborhood radius (default: 0.5)  
- `min_samples`: Minimum samples to form a core point (default: 5)  

### Hierarchical (Agglomerative)
A hierarchical clustering algorithm that builds a dendrogram by progressively merging the most similar clusters.

**Parameters:**
- `n_clusters`: Final number of clusters  
- `linkage`: Linkage metric (`average`, `single`, `complete`)  

### Auto Clustering
Automatically detects the optimal number of clusters using the elbow method.

## Configuration

The following options are available in the `config.py` file:

```python
# Clustering
clustering_enabled: bool = False          # Enable automatic clustering
clustering_method: str = "auto"           # Method: auto, kmeans, dbscan, hierarchical
clustering_min_clusters: int = 2          # Minimum number of clusters
clustering_max_clusters: int = 50         # Maximum number of clusters
```

## API Endpoints

### Run Clustering
```
POST /api/v1/clustering/run
```
Performs clustering on all fragments.

**Query parameters:**
- `task_type` (optional): Filter by task type  
- `method` (optional): Override clustering method  

**Response:**
```json
{
  "message": "Clustered 150 fragments into 8 clusters",
  "n_fragments": 150,
  "n_clusters": 8,
  "method": "auto",
  "cluster_mapping": {"fid1": 0, "fid2": 3, ...}
}
```

### Cluster Info
```
GET /api/v1/clustering/info
```
Returns detailed information about each cluster.

**Response:**
```json
[
  {
    "cluster_id": 0,
    "size": 25,
    "fragment_ids": ["fid1", "fid2", ...],
    "centroid": [0.1, 0.2, ...]
  }
]
```

### Similar Fragments in Cluster
```
GET /api/v1/clustering/{fragment_id}/similar
```
Finds similar fragments within the same cluster.

**Parameters:**
- `limit`: Maximum number of results (default: 10)

## Programmatic Usage

```python
from skill_fragment_engine.retrieval.clustering import ClusteringService

# Create service
svc = ClusteringService(method="auto")

# Run clustering
embeddings = {
    "frag_1": [0.1, 0.2, ...],
    "frag_2": [0.15, 0.25, ...],
    ...
}
cluster_mapping = svc.cluster_fragments(embeddings)

# Get cluster info
cluster_info = svc.get_cluster_info(embeddings)

# Find similar fragments in cluster
similar = svc.find_similar_in_cluster("frag_1", cluster_mapping, embeddings)
```

## Benefits

1. **Organization**: Automatically groups similar fragments.  
2. **Efficient Retrieval**: Searches are performed first within the relevant cluster.  
3. **Analysis**: Provides statistics on fragment distribution.  
4. **Redundancy Reduction**: Identifies clusters containing overly similar fragments.  

