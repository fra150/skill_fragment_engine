# Skill Fragment Engine (SFE) - Usage Guide

## Overview

Skill Fragment Engine is a "cognitive cache" layer for AI agents that implements verified reuse of results. It follows the principle: **LOOK BEFORE YOU THINK**.

## Core Workflow

1. **LOOK**: Search for exact match, similar match, or semantic match
2. **DECIDE**: Choose REUSE, ADAPT, or RECOMPUTE
3. **EXECUTE**: Return cached output, modify it, or compute fresh
4. **CAPTURE**: Store the new fragment for future reuse

## Decision Types

| Decision | Cost | Description |
|----------|------|-------------|
| REUSE | $0.000002 | Exact or near-exact match, returns cached output |
| ADAPT | $0.0021 | Similar match needs modifications (heuristics or LLM) |
| RECOMPUTE | $0.021 | No match found, fresh LLM computation required |

## Key Modules

### Execution Engine (`execution/engine.py`)
- Main entry point for task execution
- `ExecutionEngine.execute(request)` - Execute a task through SFE
- Returns `ExecutionResult` with decision, output, cost_saved, metadata

### Fragment Store (`store.py`)
- Manages fragment persistence (JSON)
- Methods: `get()`, `add()`, `search()`, `update()`, `delete()`
- Located at: `./data/fragments.json`

### Vector Store (`retrieval/vector_store.py`)
- FAISS-based semantic search
- Supports IVF-PQ and OPQ indexing for large-scale
- Methods: `add()`, `search()`, `save()`, `load()`

### Retrieval Matcher (`retrieval/matcher.py`)
- Combines exact, keyword, and semantic matching
- Configurable similarity algorithms: Jaccard, Cosine, Dice

### Clustering (`retrieval/clustering.py`)
- Methods: K-Means, DBSCAN, Hierarchical, Auto
- Auto-detection of optimal cluster count

### Services
- `llm_service.py` - OpenAI and Anthropic integration with retry logic
- `versioning_service.py` - Version history, branches, rollback
- `feedback_service.py` - Quality scoring, adaptive thresholds
- `transfer_learning_service.py` - Pattern learning
- `rollback_service.py` - Automatic rollback on failures
- `encryption_service.py` - Field-level encryption
- `rbac_service.py` - Role-based access control
- `audit_service.py` - Complete operation tracking
- `anonymization_service.py` - PII detection and redaction

## API Usage

### Execute a Task
```python
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.core.models import ExecutionRequest

engine = ExecutionEngine()

req = ExecutionRequest(
    task_type="code_generation",
    prompt="Write a function to reverse a string",
    context={"language": "python"},
    options={"capture_fragment": True}
)

result = await engine.execute(req)
print(result.decision, result.output, result.metadata.cost_saved)
```

### Search Fragments
```python
from skill_fragment_engine.store import FragmentStore

store = FragmentStore()
fragments = store.search_by_similarity("reverse a string", top_k=5)
```

### Run Clustering
```python
from skill_fragment_engine.retrieval.clustering import ClusteringService

svc = ClusteringService(method="auto")
cluster_mapping = svc.cluster_fragments(embeddings)
```

### Submit Feedback
```python
from skill_fragment_engine.services.feedback_service import FeedbackService

feedback_svc = FeedbackService()
await feedback_svc.submit_feedback(
    fragment_id="uuid",
    feedback_type="positive",
    score=0.9,
    comment="Great result!"
)
```

## Configuration (.env)

Key settings in `core/config.py`:
- `FRAGMENT_STORE_PATH` - JSON file path
- `VECTOR_STORE_PATH` - FAISS index path
- `SIMILARITY_ALGORITHM` - jaccard, cosine, dice
- `VECTOR_USE_IVF_PQ` - Enable IVF-PQ indexing
- `VECTOR_USE_OPQ` - Enable OPQ optimization
- `CLUSTERING_ENABLED` - Enable clustering
- `LLM_API_KEY` - OpenAI/Anthropic key

## Architecture

```
INPUT
  ▼
SKILL MATCHER LAYER
  - Exact match (FragmentStore JSON)
  - Similar match (keyword overlap)
  - Semantic match (FAISS + embeddings)
  ▼
VALIDATOR ENGINE
  - exact → REUSE
  - similar + valid → REUSE
  - similar + needs changes → ADAPT
  - no match → RECOMPUTE
  ▼
EXECUTION
  - REUSE: returns cached output
  - ADAPT: modifies cached output
  - RECOMPUTE: fresh LLM computation
  ▼
CAPTURE
  - stores fragment to JSON
  - indexes embedding to FAISS
```

## Testing

```bash
python -m pytest -q
```

## Linting

```bash
ruff check .
mypy .
```

## Storage

- `./data/fragments.json` - Serialized SkillFragments
- `./data/faiss/index.faiss` - FAISS vector index
- `./data/faiss/id_map.json` - Fragment ID mappings
