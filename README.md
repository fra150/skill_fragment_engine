# Skill Fragment Engine (SFE)

A “cognitive cache” layer for AI agents with **verified reuse** of results.

Core principle: **LOOK BEFORE YOU THINK**. Before executing any task, SFE:
1) looks for an exact match (0 LLM tokens),
2) looks for similar matches (0 LLM tokens),
3) injects “cognitive history” into the context,
4) decides REUSE / ADAPT / RECOMPUTE,
5) saves the new trace (fragment).

## Current Status (Results)

- Local fragment persistence (JSON): `./data/fragments.json`
- **Exact** + **similar** lookup (keyword overlap) at zero cost (no LLM calls)
- Operational pipeline: Retrieval → Validation → Execution → Capture
- FastAPI API ready:
  - `POST /api/v1/execute`
  - `GET /api/v1/fragment/search`
  - `GET /api/v1/health`
- Offline mode:
  - if `LLM_API_KEY` is not provided, deterministic embeddings (hash → vector) are used and semantic retrieval is disabled
  - “RECOMPUTE” execution currently uses a mock response (wiring ready to connect a real LLM)
- Tests: `python -m pytest -q` → 36 passed

## Architecture (Implemented)

```
INPUT
  │
  ▼
SKILL MATCHER LAYER
  - Exact match (FragmentStore JSON)
  - Similar match (keyword overlap, FragmentStore JSON)
  - Semantic match (FAISS + embeddings)  [only if LLM_API_KEY]
  │
  ▼
VALIDATOR ENGINE
  - exact → REUSE
  - otherwise: context distance + thresholds per task_type → REUSE/ADAPT/RECOMPUTE
  │
  ▼
EXECUTION
  - REUSE: returns cached output
  - ADAPT: modifies cached output (heuristics)
  - RECOMPUTE: “LLM call” (currently mocked) with cognitive history in context
  │
  ▼
CAPTURE
  - stores fragment to ./data/fragments.json
  - indexes embedding to ./data/faiss (when capturing a new fragment)
```

## Quick Start (Local)

### Install

```bash
pip install -r requirements.txt
```

### Start server (Windows / PowerShell)

This project uses a `src/` layout. If you are not running an editable install, set `PYTHONPATH=src`.

```powershell
$env:PYTHONPATH="src"
python -m uvicorn skill_fragment_engine.main:app --host 0.0.0.0 --port 8000
```

- Home: http://localhost:8000/
- Swagger: http://localhost:8000/docs

## API

### Execute a task

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

Running the same request twice will try to hit REUSE (exact match) once the fragment is stored.

### Search fragments

```bash
curl "http://localhost:8000/api/v1/fragment/search?query=reverse%20a%20string&top_k=5"
```

## Python Usage

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

## On-disk storage

- `./data/fragments.json` holds:
  - the serialized `SkillFragment`
  - original prompt
  - deterministic input hash
- `./data/faiss/` holds `index.faiss` and `id_map.json`

## Configuration (.env)

Example:

```env
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

FRAGMENT_STORE_PATH=./data/fragments.json
VECTOR_STORE_PATH=./data/faiss

SIMILARITY_TOP_K=10
MIN_SIMILARITY_SCORE=0.5
KEYWORD_SIMILARITY_MIN_OVERLAP=0.3
```

Without `LLM_API_KEY`:
- no external embedding calls
- semantic retrieval is disabled

## Development

### Tests

```bash
python -m pytest -q
```

### Dev tooling (ruff/mypy)

```bash
pip install -e ".[dev]"
```

## Available Endpoints

| Method | Endpoint                         | Status                   |
| ------ | -------------------------------- | ------------------------ |
| GET    | `/api/v1/health`                 | ok                       |
| POST   | `/api/v1/execute`                | ok                       |
| GET    | `/api/v1/fragment/search`        | ok                       |
| GET    | `/api/v1/fragment/{id}`          | placeholder (404)        |
| POST   | `/api/v1/fragment`               | placeholder (501)        |
| POST   | `/api/v1/fragment/{id}/validate` | stub (always valid=true) |
| GET    | `/api/v1/metrics`                | stub (zeros)             |
| POST   | `/api/v1/admin/prune`            | stub                     |
| POST   | `/api/v1/admin/decay`            | stub                     |

## License

MIT open source license
