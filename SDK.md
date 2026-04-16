# Skill Fragment Engine - SDK Usage

## Installazione

```bash
pip install skill-fragment-engine
```

## Utilizzo Rapido

```python
from skill_fragment_engine import SkillFragmentEngine

# Inizializza il motore
sfe = SkillFragmentEngine()

# Esegue un task (ricerca automaticamente frammenti simili)
result = await sfe.execute(
    task_type="code_generation",
    prompt="Write a function to reverse a string in Python",
    context={"language": "python"}
)

print(f"Decision: {result.decision}")  # REUSE, ADAPT, o RECOMPUTE
print(f"Output: {result.output}")
print(f"Cost saved: ${result.cost_saved:.6f}")
```

## API Completa

### ExecutionEngine

```python
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.core.models import ExecutionRequest

engine = ExecutionEngine()

request = ExecutionRequest(
    task_type="text_generation",
    prompt="Write a professional email",
    context={"tone": "formal", "language": "en"},
    options={
        "capture_fragment": True,
        "force_recompute": False
    }
)

result = await engine.execute(request)
```

### Fragment Store

```python
from skill_fragment_engine.store import FragmentStore

store = FragmentStore()

# Ricerca per similarità
fragments = store.search_by_similarity(
    query="reverse string python",
    top_k=10,
    min_score=0.5
)

# Ricerca esatta
fragment = store.get_by_hash(content_hash)

# Aggiungi frammento manualmente
store.add(fragment)
```

### Vector Store con FAISS

```python
from skill_fragment_engine.retrieval.vector_store import VectorStore

vector_store = VectorStore(
    embedding_dim=1536,
    use_ivf_pq=True,  # Per grandi volumi
    nlist=100
)

# Aggiungi embedding
vector_store.add(fragment_id, embedding)

# Ricerca
results = vector_store.search(query_embedding, k=10)
```

### Clustering

```python
from skill_fragment_engine.retrieval.clustering import ClusteringService

clustering = ClusteringService(method="auto")

# Esegui clustering
cluster_mapping = clustering.cluster_fragments(embeddings)

# Info sui cluster
info = clustering.get_cluster_info(embeddings)

# Frammenti simili nello stesso cluster
similar = clustering.get_similar_in_cluster(fragment_id, embeddings)
```

### Servizi

```python
# Versioning
from skill_fragment_engine.services.versioning_service import VersioningService
versioning = VersioningService()

versions = await versioning.get_version_history(fragment_id)
await versioning.rollback(fragment_id, "v2")

# Feedback
from skill_fragment_engine.services.feedback_service import FeedbackService
feedback = FeedbackService()

await feedback.submit_feedback(
    fragment_id=fragment_id,
    feedback_type="positive",
    score=0.9
)

# Transfer Learning
from skill_fragment_engine.services.transfer_learning_service import TransferLearningService
tl = TransferLearningService()

patterns = await tl.get_top_patterns(limit=10)
suggestions = await tl.suggest_parameters(task_type, context)

# Rollback
from skill_fragment_engine.services.rollback_service import RollbackService
rollback = RollbackService()

stats = await rollback.get_stats()
```

## Configurazione

Crea un file `.env`:

```env
# LLM
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4
LLM_BASE_URL=https://api.openai.com/v1

# Storage
FRAGMENT_STORE_PATH=./data/fragments.json
VECTOR_STORE_PATH=./data/faiss

# Retrieval
SIMILARITY_ALGORITHM=jaccard
SIMILARITY_TOP_K=10
MIN_SIMILARITY_SCORE=0.5

# Vector Store
VECTOR_USE_IVF_PQ=true
VECTOR_USE_OPQ=true
VECTOR_IVF_NLIST=100

# Clustering
CLUSTERING_ENABLED=true
CLUSTERING_METHOD=auto
```

## Server API

Avvia il server:

```bash
python -m skill_fragment_engine.main
```

Endpoint disponibili:
- `POST /api/v1/execute` - Esegui task
- `GET /api/v1/fragment/search` - Cerca frammenti
- `POST /api/v1/clustering/run` - Esegui clustering
- `POST /api/v1/feedback` - Invia feedback
- `GET /api/v1/metrics` - Metriche sistema

Documentazione completa: http://localhost:8000/docs
