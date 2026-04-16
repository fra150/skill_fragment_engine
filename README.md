<div align="center">
  <h1>🧠 Skill Fragment Engine (SFE)</h1>
  <p><em>A cognitive caching layer that empowers AI agents to <strong>Reuse</strong>, <strong>Adapt</strong>, and <strong>Evolve</strong> rather than blindly recomputing.</em></p>
  
  [![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393.svg)](https://fastapi.tiangolo.com)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
</div>

---

## 💡 The Core Principle: *Look Before You Think*

Why pay for expensive LLM tokens and latency to solve the exact same problem twice? 

Before executing any task, **SFE** intercepts the request and performs a cognitive lookup:
1. **Zero-cost exact matching** (0 LLM tokens, 0 API calls).
2. **Advanced similarity matching** (Jaccard, Cosine, Dice) and semantic vector search (FAISS).
3. **Cognitive Injection**: Injects past successful problem-solving history directly into the context.
4. **Intelligent Decision Engine**: Autonomously decides whether to `REUSE`, `ADAPT`, or `RECOMPUTE`.
5. **Continuous Learning**: Saves the new execution trace as a highly reusable *Skill Fragment*.

---

## 🚀 Key Capabilities & Architecture

SFE is designed for massive scale, deep integration with AI ecosystems, and enterprise-grade governance.

### 🔌 AI Tool Integration & Ecosystem
- **AI Coding Assistants Ready**: Pre-built skills and adapters for tools like **[OpenCode](https://opencode.dev/)**, **Claude Code**, and **ClawCode**. Just load the SFE skill and watch your AI agent become instantly smarter and cheaper.
- **Polyglot SDKs**: Native clients available for **Python**, **JavaScript/TypeScript**, and **Java/Kotlin**.
- **Plugin System**: Easily plug SFE into frameworks like **LangChain** and **LlamaIndex** using the provided adapters in `plugins/examples/`.

### 🧠 Advanced Cognitive Retrieval
- **Hybrid Search**: Combines deterministic keyword overlap (zero-cost) with deep semantic embeddings.
- **Scalable Vector Store**: Native FAISS integration optimized with **IVF-PQ** (Inverted File System with Product Quantization) and **OPQ** for handling massive vector datasets with sub-millisecond latency.
- **Automatic Clustering**: Built-in K-Means, DBSCAN, and Hierarchical clustering (with auto-detection via elbow method) to discover patterns in your AI's problem-solving behavior.

### 📈 Evolution & Transfer Learning
- **Feedback Loop**: Users and agents can submit positive/negative feedback. SFE dynamically adjusts quality scores and matching thresholds (adaptive strictness).
- **Transfer Learning**: Learns which adaptation parameters work best for specific tasks and proactively suggests them for future executions.
- **Automatic Rollback**: Detects failing fragments and autonomously rolls back to the last known "safe" version.

### 🛡️ Enterprise Governance & Privacy
- **Versioning & Branching**: Every fragment modification is tracked. Support for branches, version history, and manual rollback.
- **Decay & Pruning**: Stale or failing knowledge slowly "decays" and gets automatically pruned.
- **Privacy First**: Built-in PII anonymization (SSN, credit cards, emails) and field-level AES-128 encryption.
- **RBAC & Audit**: Role-Based Access Control and complete audit trailing for every operation.

---

## ⚡ Quick Start

### 1. Local Setup

```bash
# Clone and install dependencies
git clone https://github.com/fra150/skill_fragment_engine.git
cd skill_fragment_engine
pip install -r requirements.txt
```

### 2. Start the Engine

```powershell
# Windows (PowerShell)
$env:PYTHONPATH="src"
python -m uvicorn skill_fragment_engine.main:app --host 0.0.0.0 --port 8000
```
*Or use Docker:*
```bash
docker-compose up -d
```

- **API Base**: `http://localhost:8000/api/v1`
- **Interactive Docs**: `http://localhost:8000/docs`

---

## 🛠️ Usage Example (Python)

```python
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.core.models import ExecutionRequest

engine = ExecutionEngine()

# The agent asks to solve a problem
req = ExecutionRequest(
    task_type="code_generation",
    prompt="Write a Python function to reverse a linked list",
    context={"language": "python", "framework": "standard"},
    options={"capture_fragment": True},
)

# SFE decides whether to REUSE, ADAPT, or RECOMPUTE
res = await engine.execute(req)

print(f"Decision: {res.decision}")
print(f"Saved Cost: ${res.metadata.cost_saved}")
```

---

## 🤖 Using SFE with Claude Code / OpenCode

SFE includes native skills for CLI AI coding agents. This allows your agent to query its own cognitive cache before writing code.

1. Locate the `skills/skill-fragment-engine/` directory.
2. Load the `skill.yaml` into your agent (e.g., placing it in your `.opencode/skills/` directory).
3. The agent will automatically invoke the `skill-fragment-engine` tool to check for existing solutions before consuming tokens.

---

## 📊 Telemetry & Sharding
SFE is built to scale. It features a complete `MetricsCollector` (tracking hit rates, latency percentiles, memory usage, and cost savings) and a **Sharding Service** skeleton (Hash-based, Task-type based, Time-based) to distribute knowledge across distributed environments.

## ✅ Test Results (Real OpenAI API)

| Test Case              | Decision | Tokens | Cost Saved |
|------------------------|----------|--------|------------|
| Fibonacci (first)      | recompute| 377    | $0.00      |
| Fibonacci (cached)     | REUSE    | 0      | $0.021     |
| Similar prompt         | recompute| 182    | $0.00      |
| Text summarization     | recompute| 467    | $0.00      |
| Summarization (cached) | REUSE    | 0      | $0.021     |

**Performance**: REUSE saves ~$0.021 per request (full LLM cost avoided)  
**Latency**: REUSE ~5ms vs RECOMPUTE ~8000ms (1600x faster)

## 📄 License

MIT Open Source License.

---
*Developed by Francesco Bulla (FB) & AI Pair Programmer.*