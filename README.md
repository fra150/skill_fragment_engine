# Skill Fragment Engine (SFE)

A "cognitive cache" layer for AI agents with **verified reuse** of results.

Core principle: **LOOK BEFORE YOU THINK**. Before executing any task, SFE:
1. Looks for an exact match (0 LLM tokens)
2. Looks for similar matches (0 LLM tokens)
3. Injects "cognitive history" into the context
4. Decides REUSE / ADAPT / RECOMPUTE
5. Saves the new trace (fragment)

## Features

### Core Capabilities
- **Local fragment persistence** (JSON): `./data/fragments.json`
- **Exact + similar lookup** (keyword overlap) at zero cost
- **Semantic retrieval** with FAISS vector store
- **Advanced similarity algorithms**: Jaccard, Cosine, Dice
- **IVF-PQ/OPQ indexing** for large-scale vector datasets

### Security & Privacy
- **Encryption**: Field-level encryption with Fernet (AES-128 + HMAC)
- **RBAC**: Role-based access control (Admin, Power User, User, ReadOnly, Guest)
- **Audit Logging**: Complete operation tracking for compliance
- **Anonymization**: PII detection and redaction

### Decision Engine
- **REUSE**: Returns cached output (0.000002$ cost)
- **ADAPT**: Modifies cached output with heuristics (0.0021$ cost)
- **RECOMPUTE**: Fresh LLM computation (0.021$ cost)
- Context-aware adaptation with style transfer

### Advanced Services
- **Versioning**: Full version history, branches, rollback
- **Feedback System**: Quality scoring, adaptive thresholds
- **Transfer Learning**: Pattern learning for better adaptations
- **Rollback**: Automatic rollback on repeated failures

### Clustering
- **K-Means**, **DBSCAN**, **Hierarchical** clustering
- Auto-detection of optimal cluster count (elbow method)
- Find similar fragments within same cluster

## Quick Start

### Local Installation

```bash
pip install -r requirements.txt
```

### Start Server

```powershell
$env:PYTHONPATH="src"
python -m uvicorn skill_fragment_engine.main:app --host 0.0.0.0 --port 8000
```

- Home: http://localhost:8000/
- Swagger: http://localhost:8000/docs

### Docker

```bash
# Build
docker build -t skill-fragment-engine .

# Run
docker run -d -p 8000:8000 skill-fragment-engine

# Or with docker-compose
docker-compose up -d
```

## Configuration (.env)

```env
# LLM
LLM_API_KEY=sk-...
LLM_MODEL=gpt-5
LLM_BASE_URL=https://api.openai.com/v1

# Storage
FRAGMENT_STORE_PATH=./data/fragments.json
VECTOR_STORE_PATH=./data/faiss
EMBEDDING_DIM=1536

# Retrieval
SIMILARITY_TOP_K=10
MIN_SIMILARITY_SCORE=0.5
KEYWORD_SIMILARITY_MIN_OVERLAP=0.3
SIMILARITY_ALGORITHM=jaccard

# Vector Store Optimization
VECTOR_USE_IVF_PQ=false
VECTOR_USE_OPQ=false
VECTOR_IVF_NLIST=100
VECTOR_NPROBE=10
VECTOR_PQ_M=16
VECTOR_PQ_NBITS=8

# Clustering
CLUSTERING_ENABLED=false
CLUSTERING_METHOD=auto
CLUSTERING_MIN_CLUSTERS=2
CLUSTERING_MAX_CLUSTERS=50

# Redis (optional)
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=false
```

## API Endpoints

### Execution
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/execute` | Execute a task through SFE |

### Fragments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/fragment/search` | Search fragments by similarity |
| GET | `/api/v1/fragments/{id}` | Get fragment by ID |
| POST | `/api/v1/fragment` | Create fragment manually |
| POST | `/api/v1/fragment/{id}/validate` | Validate fragment |
| GET | `/api/v1/fragments/{id}/versions` | Get version history |
| POST | `/api/v1/fragments/{id}/versions` | Create new version |
| POST | `/api/v1/fragments/{id}/rollback/{version}` | Rollback to version |
| GET | `/api/v1/fragments/{id}/branches` | Get branches |
| GET | `/api/v1/fragments/{id}/quality` | Get quality score |

### Clustering
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/clustering/run` | Run clustering on all fragments |
| GET | `/api/v1/clustering/info` | Get cluster information |
| GET | `/api/v1/clustering/{id}/similar` | Get similar fragments in cluster |

### Feedback
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/feedback` | Submit feedback on execution |
| GET | `/api/v1/feedback/stats` | Get feedback statistics |
| GET | `/api/v1/feedback/recent` | Get recent feedback |

### Versioning
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/fragments/{id}/versions` | Get version history |
| POST | `/api/v1/fragments/{id}/versions` | Create new version |
| POST | `/api/v1/fragments/{id}/rollback/{version}` | Rollback |
| GET | `/api/v1/fragments/{id}/branches` | List branches |

### Rollback
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/rollback/stats` | Get rollback statistics |
| GET | `/api/v1/rollback/history` | Get rollback history |

### Transfer Learning
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/transfer-learning/stats` | Get pattern statistics |
| GET | `/api/v1/transfer-learning/patterns` | Get top patterns |
| POST | `/api/v1/transfer-learning/learn` | Record adaptation |
| GET | `/api/v1/transfer-learning/suggest` | Get suggested parameters |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/metrics` | System metrics |
| POST | `/api/v1/admin/prune` | Trigger pruning |
| POST | `/api/v1/admin/decay` | Trigger decay calculation |
| GET | `/api/v1/health` | Health check |

## Usage Examples

### Execute a Task

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "code_generation",
    "prompt": "Write a function to reverse a string in Python",
    "context": {"language": "python"},
    "options": {"capture_fragment": true}
  }'
```

### Search Fragments

```bash
curl "http://localhost:8000/api/v1/fragment/search?query=reverse%20a%20string&top_k=5"
```

### Run Clustering

```bash
curl -X POST "http://localhost:8000/api/v1/clustering/run?method=auto"
```

### Submit Feedback

```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_type": "positive",
    "score": 0.9,
    "fragment_id": "uuid-here",
    "comment": "Great result!"
  }'
```

### Python Usage

```python
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.core.models import ExecutionRequest

engine = ExecutionEngine()

req = ExecutionRequest(
    task_type="code_generation",
    prompt="Write a function to reverse a string in Python",
    context={"language": "python"},
    options={"capture_fragment": True},
)

res = await engine.execute(req)
print(res.decision, res.metadata.cost_saved)
```

### Clustering in Python

```python
from skill_fragment_engine.retrieval.clustering import ClusteringService

svc = ClusteringService(method="auto")

embeddings = {
    "frag_1": [0.1, 0.2, ...],
    "frag_2": [0.15, 0.25, ...],
}

cluster_mapping = svc.cluster_fragments(embeddings)
cluster_info = svc.get_cluster_info(embeddings)
```

## Architecture

```
INPUT
  │
  ▼
SKILL MATCHER LAYER
  - Exact match (FragmentStore JSON)
  - Similar match (keyword overlap)
  - Semantic match (FAISS + embeddings)
  │
  ▼
VALIDATOR ENGINE
  - exact → REUSE
  - similar + valid → REUSE
  - similar + needs changes → ADAPT
  - no match → RECOMPUTE
  │
  ▼
EXECUTION
  - REUSE: returns cached output
  - ADAPT: modifies cached output (heuristics + LLM)
  - RECOMPUTE: fresh LLM computation
  │
  ▼
CAPTURE
  - stores fragment to ./data/fragments.json
  - indexes embedding to ./data/faiss
```

## Development

### Tests

```bash
python -m pytest -q
```

### Dev Tools

```bash
pip install -e ".[dev]"
ruff check .
mypy .
```

## On-disk Storage

- `./data/fragments.json` - Serialized SkillFragments
- `./data/faiss/index.faiss` - FAISS vector index
- `./data/faiss/id_map.json` - Fragment ID mappings

## License

MIT open source license