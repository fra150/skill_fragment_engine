# Skill Fragment Engine (SFE) - Technical Specification

**Version:** 1.0 MVP
**Last Updated:** 2026-03-25
**Status:** Ready for Implementation

---

## 1. Concept & Vision

### 1.1 Core Idea

> "Un'AI non deve rifare, deve riconoscere quando NON serve rifare."

Skill Fragment Engine è un sistema di **Cognitive Cache** che trasforma le esecuzioni AI in unità riutilizzabili verificate. Non è una semplice cache (Redis-style), ma una **memoria operativa intelligente** che:

- Documenta il processo di esecuzione, non solo l'output
- Valida prima di riutilizzare (zero-trust approach)
- Conserva tutte le varianti per learning incrementale
- Applica governance automatica per evitare degradazione

### 1.2 Paradigm Shift

| Vecchio Paradigma | Nuovo Paradigma |
|-------------------|-----------------|
| Ogni query = nuovo LLM call | Query simili = skill riutilizzabili |
| Output = risultato | Output = risultato + pattern estratti |
| Cache = key-value | Cache = frammenti validati con contesto |
| Nessuna storia | Ritrospettiva completa di ogni esecuzione |

### 1.3 Value Proposition

- **Cost Reduction:** 50-80% su task ripetitivi
- **Latency Reduction:** 90%+ per cache hit esatti
- **Quality Improvement:** Learning implicito dalle varianti
- **Auditability:** Tracciabilità completa di ogni decisione

---

## 2. System Architecture

### 2.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INPUT FLOW                                  │
│                                                                         │
│    ┌──────────┐    ┌──────────────┐    ┌────────────────────────────┐  │
│    │  Input   │───▶│Skill Matcher │───▶│   Validator Engine        │  │
│    │ Request │    │   Layer      │    │                            │  │
│    └──────────┘    └──────────────┘    │  ┌────────────────────────┐│  │
│                                         │  │ Context Comparator    ││  │
│                                         │  │ Task Type Rules      ││  │
│                                         │  │ Decision Classifier   ││  │
│                                         │  └────────────────────────┘│  │
│                                         └─────────────┬──────────────┘  │
│                                                       │                 │
│                              ┌───────────────────────┼───────────────┐  │
│                              │                       │               │  │
│                              ▼                       ▼               ▼  │
│                         ┌─────────┐            ┌─────────┐       ┌─────────┐
│                         │  REUSE  │            │  ADAPT  │       │RECOMPUTE│
│                         │ (cached)│            │(partial)│       │ (fresh) │
│                         └────┬────┘            └────┬────┘       └────┬────┘
│                              │                       │               │    │
└──────────────────────────────┴───────────────────────┴───────────────┴────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           OUTPUT FLOW                                    │
│                                                                         │
│    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│    │ Fragment Capture │───▶│Variant Manager  │───▶│ Skill Fragment  │  │
│    │    Layer         │    │                 │    │     Store       │  │
│    └──────────────────┘    └─────────────────┘    └────────┬────────┘  │
│                                                             │           │
└─────────────────────────────────────────────────────────────┼───────────┘
                                                              │
                                                              ▼
                                                    ┌─────────────────┐
                                                    │ Governance      │
                                                    │ Layer           │
                                                    └─────────────────┘
```

### 2.2 Component Overview

| Component | Responsibility | Key Technologies |
|-----------|---------------|-----------------|
| **Skill Matcher Layer** | Exact + semantic search per candidati | Hash (exact), FAISS (semantic) |
| **Validator Engine** | Decision: reuse/adapt/recompute | Rule-based + thresholds |
| **Execution Engine** | Esecuzione del percorso scelto | Python async |
| **Fragment Capture Layer** | Estrazione pattern + ritrospettiva | Task-specific extractors |
| **Variant Manager** | Gestione versioni e varianti | Graph-based versioning |
| **Skill Fragment Store** | Persistenza frammenti | PostgreSQL + FAISS |
| **Governance Layer** | Decay, pruning, scoring | Scheduled jobs |

---

## 3. Data Models

### 3.1 Core Entities

#### SkillFragment (Primary Entity)

```python
class SkillFragment:
    fragment_id: UUID
    task_type: str  # code_generation, text_summarization, data_extraction, etc.

    # Input Signature
    input_signature: InputSignature
    #   - prompt_hash: str (SHA-256)
    #   - context_hash: str (SHA-256)
    #   - parameters: dict

    # Output Schema
    output_schema: OutputSchema
    #   - result: Any (output completo)
    #   - fragment_patterns: list[FragmentPattern]
    #   - process_steps: list[str]
    #   - output_hash: str

    # Validation History
    validation_history: list[ValidationRecord]
    #   - timestamp: datetime
    #   - validation_type: str
    #   - context_distance: float
    #   - outcome: str

    # Metrics
    metrics: FragmentMetrics
    #   - creation_cost: float
    #   - creation_latency: float
    #   - reuse_count: int
    #   - adapt_count: int
    #   - failure_count: int
    #   - avg_adaptation_cost: float
    #   - total_cost_saved: float

    # Versioning
    version_chain: list[UUID]  # parent fragment IDs
    variants: list[UUID]  # child variant IDs

    # Lifecycle
    created_at: datetime
    updated_at: datetime
    decay_score: float  # 0.0 - 1.0
    is_active: bool
    quality_score: float  # 0.0 - 1.0
```

#### FragmentPattern

```python
class FragmentPattern:
    pattern_id: UUID
    fragment_id: UUID
    type: str  # algorithm, template, structure, heuristic
    content: str
    abstraction_level: float  # 0.0 (specific) - 1.0 (generalizable)
    dependencies: list[str]
    constraints: list[str]
    confidence: float
    tested_on: list[UUID]
```

#### Variant

```python
class Variant:
    variant_id: UUID
    parent_fragment_id: UUID
    created_from: str  # adaptation, failure_recovery, manual_improvement
    changes: VariantChanges
    #   - diff_type: str
    #   - before: dict
    #   - after: dict
    reason: str
    validation_result: str  # approved, rejected, needs_review
    performance_delta: dict
    created_at: datetime
```

#### ValidationRecord

```python
class ValidationRecord:
    record_id: UUID
    fragment_id: UUID
    timestamp: datetime
    validation_type: str  # context_comparison, pattern_match, user_feedback
    context_distance: float
    outcome: str  # reused_successfully, adapted, failed, recomputed
    cost_saved: float
    latency_saved: float
```

---

## 4. API Specification

### 4.1 Core Endpoints

#### POST /api/v1/execute

Execute a task with SFE optimization.

**Request:**
```json
{
  "task_type": "code_generation",
  "prompt": "Write a function to...",
  "context": {
    "language": "python",
    "style": "functional"
  },
  "parameters": {},
  "options": {
    "allow_adaptation": true,
    "allow_recompute": true,
    "capture_fragment": true
  }
}
```

**Response:**
```json
{
  "execution_id": "uuid",
  "decision": "reuse|adapt|recompute",
  "result": {...},
  "metadata": {
    "fragment_id": "uuid (if reused/adapted)",
    "variant_id": "uuid (if adapted)",
    "cost": 0.002,
    "latency_ms": 45,
    "cost_saved": 0.018,
    "decision_reason": "..."
  }
}
```

#### POST /api/v1/fragment

Create a new fragment manually (bypass execution).

**Request:**
```json
{
  "task_type": "...",
  "input_signature": {...},
  "output_schema": {...}
}
```

#### GET /api/v1/fragment/{fragment_id}

Get fragment details.

#### GET /api/v1/fragment/search

Search fragments by similarity.

**Query Parameters:**
- `q`: Text query (embedded)
- `task_type`: Filter by type
- `top_k`: Number of results (default 5)
- `min_score`: Minimum similarity score

#### POST /api/v1/fragment/{fragment_id}/validate

Trigger re-validation of a fragment.

#### GET /api/v1/metrics

Get system-wide metrics.

**Response:**
```json
{
  "total_fragments": 15432,
  "active_fragments": 12300,
  "reuse_rate": 0.67,
  "avg_cost_per_request": 0.0034,
  "total_cost_saved": 4521.34,
  "latency_p50_ms": 23,
  "latency_p99_ms": 156
}
```

#### POST /api/v1/admin/prune

Trigger manual pruning cycle.

#### POST /api/v1/admin/decay

Trigger manual decay recalculation.

---

## 5. Validator Engine - Detailed Logic

### 5.1 Decision Tree

```
START: Input arrives
│
├─▶ [1] EXACT MATCH CHECK
│    if input_signature_hash IN exact_match_index:
│       return REUSE (direct)
│    else:
│       continue
│
├─▶ [2] SEMANTIC SEARCH
│    candidates = vector_search(top_k=10)
│    if candidates.is_empty():
│       return RECOMPUTE
│    else:
│       continue
│
├─▶ [3] CONTEXT COMPARISON
│    for candidate in candidates:
│       distance = context_distance(new_input, candidate.input)
│       candidate.distance = distance
│    │
│    best = min(candidates, key=distance)
│
├─▶ [4] THRESHOLD EVALUATION
│    threshold = THRESHOLDS[task_type]
│    │
│    if best.distance <= threshold.exact_match:
│       return REUSE
│    │
│    elif best.distance <= threshold.adapt_match:
│       if adaptation_cost < recompute_cost:
│          return ADAPT
│       else:
│          return RECOMPUTE
│    │
│    else:
│       return RECOMPUTE
```

### 5.2 Task-Type Thresholds

| Task Type | Exact Match | Adapt Match | Adaptation Allowed |
|-----------|-------------|-------------|-------------------|
| `code_generation` | distance ≤ 0.05 | distance ≤ 0.15 | Yes (params only) |
| `text_summarization` | semantic ≥ 0.95 | semantic ≥ 0.80 | Limited (style) |
| `data_extraction` | schema match | distance ≤ 0.10 | No |
| `classification` | exact | N/A | No |
| `translation` | source_hash match | distance ≤ 0.05 | Yes (style/tense) |
| `question_answering` | semantic ≥ 0.92 | semantic ≥ 0.75 | Limited |

### 5.3 Context Distance Calculation

```python
def calculate_context_distance(input_a: dict, input_b: dict) -> float:
    """
    Calcola distanza tra due input.
    Peso: prompt (40%), context (35%), parameters (25%)
    """
    prompt_distance = cosine_distance(
        embed(input_a["prompt"]),
        embed(input_b["prompt"])
    )

    context_distance = structural_distance(
        input_a.get("context", {}),
        input_b.get("context", {})
    )

    params_distance = jaccard_distance(
        set(input_a.get("parameters", {}).keys()),
        set(input_b.get("parameters", {}).keys())
    )

    return (
        0.40 * prompt_distance +
        0.35 * context_distance +
        0.25 * params_distance
    )
```

---

## 6. Fragment Capture Layer

### 6.1 Process Retrospector

Every execution generates a "retrospective" that documents HOW the result was achieved:

```python
class ProcessRetrospector:
    """
    Capture the complete execution process as a fragment.
    """

    async def capture(self, execution: Execution) -> SkillFragment:
        # 1. Extract input signature
        input_sig = self._extract_input_signature(execution)

        # 2. Extract patterns from output
        patterns = await self.pattern_extractor.extract(
            output=execution.result,
            task_type=execution.task_type
        )

        # 3. Document process steps
        steps = self._document_steps(execution)

        # 4. Build output schema
        output_schema = OutputSchema(
            result=execution.result,
            fragment_patterns=patterns,
            process_steps=steps,
            output_hash=hash(execution.result)
        )

        # 5. Create fragment
        fragment = SkillFragment(
            fragment_id=uuid4(),
            task_type=execution.task_type,
            input_signature=input_sig,
            output_schema=output_schema,
            metrics=FragmentMetrics(
                creation_cost=execution.token_cost,
                creation_latency=execution.latency
            ),
            created_at=now(),
            decay_score=1.0,  # Fresh fragment = max score
            is_active=True
        )

        return fragment
```

### 6.2 Pattern Extractors

Each task type has a specialized pattern extractor:

#### Code Pattern Extractor

```python
class CodePatternExtractor:
    """
    Extracts reusable patterns from code generation output.
    """

    def extract(self, code: str, language: str) -> list[FragmentPattern]:
        patterns = []

        # 1. Functions as atomic patterns
        functions = self._extract_functions(code, language)
        for func in functions:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type="algorithm",
                content=func.source,
                abstraction_level=self._calculate_abstraction(func),
                constraints=[f"language={language}"],
                confidence=self._estimate_confidence(func)
            ))

        # 2. Class structures
        classes = self._extract_classes(code, language)
        for cls in classes:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type="structure",
                content=cls.definition,
                abstraction_level=0.6,
                dependencies=[p.pattern_id for p in patterns if cls.uses(p)],
                confidence=0.8
            ))

        # 3. Algorithm patterns (sorting, searching, etc.)
        algorithms = self._detect_algorithms(code)
        for algo in algorithms:
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type="algorithm",
                content=algo.implementation,
                abstraction_level=0.9,  # Highly generalizable
                constraints=algo.constraints,
                confidence=0.95
            ))

        return patterns
```

#### Text Pattern Extractor

```python
class TextPatternExtractor:
    """
    Extracts reusable patterns from text generation.
    """

    def extract(self, text: str, task_type: str) -> list[FragmentPattern]:
        patterns = []

        if task_type == "text_summarization":
            # Extract structural patterns
            structure = self._extract_structure(text)
            patterns.append(FragmentPattern(
                pattern_id=uuid4(),
                type="template",
                content=structure.template,
                abstraction_level=0.7,
                constraints=["summary_length_range"],
                confidence=0.85
            ))

            # Extract key phrase patterns
            key_phrases = self._extract_key_phrases(text)
            for phrase in key_phrases:
                patterns.append(FragmentPattern(
                    pattern_id=uuid4(),
                    type="heuristic",
                    content=phrase,
                    abstraction_level=0.4,  # Less generalizable
                    constraints=["topic_specific"],
                    confidence=0.6
                ))

        return patterns
```

---

## 7. Variant Management

### 7.1 Version Graph

```
                    ┌─────────────────────────────────────────┐
                    │          FRAGMENT A (v1.0)              │
                    │  Task: "Invert string function"        │
                    │  Created: 2026-01-15                   │
                    │  Reuse count: 47                       │
                    └────────────────┬──────────────────────┘
                                       │
                                       │ adaptation (params changed)
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │          VARIANT A1 (v1.1)             │
                    │  Reason: "different language style"   │
                    │  Created: 2026-02-20                   │
                    │  Performance delta: +0.05 quality     │
                    └────────────────┬──────────────────────┘
                                       │
                                       │ failure_recovery
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │          VARIANT A1-HOTFIX              │
                    │  Reason: "edge case for empty string"  │
                    │  Created: 2026-03-01                   │
                    └────────────────┬──────────────────────┘
                                       │
                                       │ manual_improvement
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │          VARIANT A1-IMPROVED (v1.2)   │
                    │  Reason: "optimized algorithm"        │
                    │  Created: 2026-03-15                   │
                    └─────────────────────────────────────────┘
```

### 7.2 Variant Creation Logic

```python
class VariantManager:

    def should_create_variant(
        self,
        fragment: SkillFragment,
        new_result: ExecutionResult,
        reason: str
    ) -> bool:
        """
        Decide if new result merits becoming a variant.
        """

        # Condition 1: Significant quality improvement
        quality_improved = (
            new_result.quality_score >
            fragment.quality_score + 0.10
        )

        # Condition 2: Successful adaptation
        successful_adaptation = (
            reason == "adaptation" and
            new_result.adaptation_delta > 0.05
        )

        # Condition 3: Failure recovery
        failure_recovered = (
            reason == "failure" and
            new_result.successful
        )

        # Condition 4: Manual approval required
        needs_review = new_result.requires_review

        return any([
            quality_improved,
            successful_adaptation,
            failure_recovered,
            needs_review
        ])

    def create_variant(
        self,
        parent: SkillFragment,
        new_result: ExecutionResult,
        reason: str
    ) -> Variant:
        """
        Create a new variant from execution result.
        """

        variant = Variant(
            variant_id=uuid4(),
            parent_fragment_id=parent.fragment_id,
            created_from=reason,
            changes=VariantChanges(
                diff_type=self._determine_diff_type(new_result),
                before=parent.output_schema.dict(),
                after=new_result.output.dict()
            ),
            reason=self._classify_reason(new_result),
            validation_result="pending",
            performance_delta={
                "quality_improvement": (
                    new_result.quality_score - parent.quality_score
                ),
                "cost_change": (
                    new_result.cost - parent.metrics.creation_cost
                )
            },
            created_at=now()
        )

        # Link variant to parent
        parent.variants.append(variant.variant_id)

        return variant
```

### 7.3 Variant Merging

When multiple variants exist, they can be merged:

```python
def merge_variants(self, variants: list[SkillFragment]) -> SkillFragment:
    """
    Merge multiple variants into a consolidated fragment.
    Use best aspects from each.
    """

    # Select best result (highest quality)
    best_result = max(variants, key=lambda v: v.quality_score)

    # Merge patterns (union with deduplication)
    merged_patterns = self._merge_patterns([
        v.output_schema.fragment_patterns for v in variants
    ])

    # Consolidate metrics
    merged_metrics = FragmentMetrics(
        creation_cost=avg([v.metrics.creation_cost for v in variants]),
        creation_latency=min([v.metrics.creation_latency for v in variants]),
        reuse_count=sum([v.metrics.reuse_count for v in variants]),
        adapt_count=sum([v.metrics.adapt_count for v in variants]),
        failure_count=min([v.metrics.failure_count for v in variants]),
        total_cost_saved=sum([v.metrics.total_cost_saved for v in variants])
    )

    return SkillFragment(
        fragment_id=uuid4(),
        task_type=best_result.task_type,
        input_signature=best_result.input_signature,
        output_schema=OutputSchema(
            result=best_result.output_schema.result,
            fragment_patterns=merged_patterns,
            process_steps=best_result.output_schema.process_steps
        ),
        metrics=merged_metrics,
        version_chain=[v.fragment_id for v in variants],
        quality_score=best_result.quality_score,
        created_at=now()
    )
```

---

## 8. Governance Layer

### 8.1 Decay Manager

```python
class DecayManager:
    """
    Skills lose weight over time.
    Decay is slowed by recent usage.
    """

    DECAY_CONFIG = {
        "code_generation": {
            "half_life_days": 90,
            "min_threshold": 0.5,
            "usage_boost_factor": 0.3
        },
        "text_summarization": {
            "half_life_days": 30,
            "min_threshold": 0.6,
            "usage_boost_factor": 0.2
        },
        "data_extraction": {
            "half_life_days": 180,
            "min_threshold": 0.7,
            "usage_boost_factor": 0.25
        },
        "classification": {
            "half_life_days": 60,
            "min_threshold": 0.55,
            "usage_boost_factor": 0.15
        }
    }

    def calculate_decay_score(self, fragment: SkillFragment) -> float:
        config = self.DECAY_CONFIG[fragment.task_type]

        # Time-based decay (exponential)
        age_days = (now() - fragment.created_at).days
        half_life = config["half_life_days"]
        time_factor = 0.5 ** (age_days / half_life)

        # Usage-based boost (recently used = less decay)
        recent_uses = self._count_recent_uses(fragment, days=30)
        usage_factor = min(1.0, recent_uses / 10)
        boost = config["usage_boost_factor"] * usage_factor

        # Calculate final score
        final_score = time_factor * (1.0 - config["usage_boost_factor"]) + boost
        final_score = max(config["min_threshold"], final_score)

        return round(final_score, 4)

    def apply_decay(self) -> int:
        """
        Apply decay to all fragments.
        Returns count of fragments updated.
        """
        fragments = self.store.get_active_fragments()
        updated = 0

        for fragment in fragments:
            old_score = fragment.decay_score
            new_score = self.calculate_decay_score(fragment)

            if old_score != new_score:
                fragment.decay_score = new_score
                fragment.updated_at = now()

                # Deactivate if below threshold
                if new_score < self.DECAY_CONFIG[fragment.task_type]["min_threshold"]:
                    fragment.is_active = False

                self.store.update(fragment)
                updated += 1

        return updated
```

### 8.2 Pruning Scheduler

```python
class PruningScheduler:

    def run_pruning_cycle(self) -> PruningReport:
        """
        Execute full pruning cycle.
        """
        report = PruningReport()

        # 1. Remove decayed fragments
        report.decay_removals = self._prune_by_decay()

        # 2. Remove duplicates (high similarity)
        report.duplicate_removals = self._prune_duplicates()

        # 3. Remove stale (never used, old)
        report.stale_removals = self._prune_stale(days=30)

        # 4. Remove low quality
        report.low_quality_removals = self._prune_low_quality(threshold=0.3)

        # 5. Remove high failure rate
        report.failure_removals = self._prune_by_failure_rate(threshold=0.1)

        return report

    def _prune_duplicates(self) -> int:
        """
        Find and remove duplicate fragments.
        Keep the one with best metrics.
        """
        fragments = self.store.get_all_fragments()
        removed = 0

        # Group by task_type and input_hash prefix
        groups = defaultdict(list)
        for f in fragments:
            key = (f.task_type, f.input_signature.prompt_hash[:8])
            groups[key].append(f)

        for group in groups.values():
            if len(group) < 2:
                continue

            # Sort by score
            ranked = sorted(
                group,
                key=lambda f: self.scoring.calculate_fragment_score(f),
                reverse=True
            )

            # Remove all but best
            for duplicate in ranked[1:]:
                self.store.delete(duplicate.fragment_id)
                removed += 1

        return removed
```

### 8.3 Scoring Calculator

```python
class ScoringCalculator:
    """
    Calculate composite score for fragment ranking.
    """

    WEIGHTS = {
        "confidence": 0.25,
        "reuse_rate": 0.25,
        "quality_trend": 0.20,
        "recency": 0.15,
        "adaptability": 0.15
    }

    def calculate_fragment_score(self, fragment: SkillFragment) -> float:
        """
        Calculate overall fragment score (0.0 - 1.0).
        """

        scores = {
            # Confidence = decay score (already normalized)
            "confidence": fragment.decay_score,

            # Reuse rate = reuse / (reuse + adapt)
            "reuse_rate": self._calculate_reuse_rate(fragment),

            # Quality trend = recent quality vs historical
            "quality_trend": self._calculate_quality_trend(fragment),

            # Recency = age factor
            "recency": self._calculate_recency_score(fragment),

            # Adaptability = how often reuse vs adapt
            "adaptability": self._calculate_adaptability(fragment)
        }

        # Weighted sum
        total = sum(
            self.WEIGHTS[k] * scores[k]
            for k in self.WEIGHTS
        )

        return round(total, 4)

    def get_top_k_for_task(
        self,
        task_type: str,
        k: int = 10
    ) -> list[SkillFragment]:
        """
        Get top K fragments for a task type.
        """
        fragments = self.store.get_by_task_type(task_type)
        scored = [
            (f, self.calculate_fragment_score(f))
            for f in fragments
        ]
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)
        return [f for f, _ in ranked[:k]]
```

---

## 9. Cost Model

### 9.1 Cost Breakdown

| Operation | Token Cost | Compute Cost | Latency |
|-----------|------------|--------------|---------|
| **New Execution** | ~$0.020 | ~$0.001 | ~500ms |
| **Exact Reuse** | ~$0.000001 | ~$0.000001 | ~5ms |
| **Semantic Reuse** | ~$0.0001 | ~$0.00001 | ~50ms |
| **Adaptation** | ~$0.002 | ~$0.0001 | ~100ms |

### 9.2 Savings Calculator

```python
def calculate_potential_savings(
    total_requests: int,
    exact_match_rate: float,
    semantic_match_rate: float,
    adaptation_rate: float,
    new_execution_cost: float = 0.021
) -> dict:

    # Count by path
    exact_count = int(total_requests * exact_match_rate)
    semantic_count = int(total_requests * semantic_match_rate)
    adapt_count = int(total_requests * adaptation_rate)
    new_count = total_requests - exact_count - semantic_count - adapt_count

    # Calculate costs
    costs = {
        "exact_reuse": exact_count * 0.000002,
        "semantic_reuse": semantic_count * 0.00011,
        "adaptation": adapt_count * 0.0021,
        "new_execution": new_count * new_execution_cost
    }

    total_cost = sum(costs.values())
    baseline_cost = total_requests * new_execution_cost

    return {
        "total_cost": total_cost,
        "baseline_cost": baseline_cost,
        "savings": baseline_cost - total_cost,
        "savings_percent": ((baseline_cost - total_cost) / baseline_cost) * 100,
        "cost_per_request": total_cost / total_requests,
        "breakdown": costs
    }
```

### 9.3 Example Scenario

```
Input:
- Total requests/day: 10,000
- Exact match: 30% (3,000)
- Semantic match: 25% (2,500)
- Adaptation: 20% (2,000)
- New execution: 25% (2,500)

Without SFE:
- Cost: 10,000 × $0.021 = $210.00/day

With SFE:
- Exact reuse: 3,000 × $0.000002 = $0.006
- Semantic reuse: 2,500 × $0.00011 = $0.275
- Adaptation: 2,000 × $0.0021 = $4.20
- New execution: 2,500 × $0.021 = $52.50
- Total: $56.98/day

Savings: $153.02/day (72.9%)
Annual savings: ~$55,850/year
```

---

## 10. Metrics & Monitoring

### 10.1 Key Metrics

```python
METRICS_CONFIG = {
    # Efficiency
    "reuse_rate": {
        "type": "gauge",
        "description": "% requests served from cache",
        "target": "> 0.50",
        "calculation": "reuse_count / total_requests"
    },

    "adaptation_rate": {
        "type": "gauge",
        "description": "% requests requiring adaptation",
        "target": "< 0.25"
    },

    # Cost
    "cost_per_request": {
        "type": "gauge",
        "description": "Average cost per request ($)",
        "baseline": 0.021,
        "target": "< 0.005
    },

    "daily_cost_savings": {
        "type": "counter",
        "description": "Cumulative cost savings ($)",
        "unit": "currency"
    },

    # Latency
    "latency_p50": {
        "type": "histogram",
        "description": "Median latency (ms)",
        "target": "< 50
    },

    "latency_p99": {
        "type": "histogram",
        "description": "99th percentile latency (ms)",
        "target": "< 200
    },

    # Quality
    "adaptation_success_rate": {
        "type": "gauge",
        "description": "% adaptations not requiring recompute",
        "target": "> 0.85"
    },

    "failure_rate": {
        "type": "gauge",
        "description": "% requests that failed",
        "target": "< 0.001
    },

    # Storage
    "fragment_count": {
        "type": "gauge",
        "description": "Active fragment count"
    },

    "storage_size_mb": {
        "type": "gauge",
        "description": "Storage size (MB)"
    },

    "pruning_rate": {
        "type": "gauge",
        "description": "Fragments removed / total per cycle",
        "target": "< 0.05
    }
}
```

### 10.2 Logging Strategy

```python
# Every request logs:
log_entry = {
    "execution_id": "uuid",
    "timestamp": "ISO-8601",
    "task_type": "string",
    "decision": "reuse|adapt|recompute",
    "fragment_id": "uuid or null",
    "variant_id": "uuid or null",
    "cost": 0.00011,
    "latency_ms": 45,
    "success": true,
    "user_feedback": null  # if provided
}

# Periodic aggregation:
aggregation = {
    "period": "hour",
    "task_type": "code_generation",
    "total_requests": 1523,
    "reuse_count": 892,
    "adapt_count": 341,
    "recompute_count": 290,
    "avg_cost": 0.0034,
    "avg_latency_ms": 38,
    "failures": 2
}
```

---

## 11. Implementation Phases

### Phase 1: Core (Days 1-10)

**Goal:** Minimal working system with exact + semantic reuse

| Day | Deliverable |
|-----|-------------|
| 1-2 | Project setup, data models, PostgreSQL schema |
| 3-4 | Fragment capture layer with basic extractors |
| 5-6 | Retrieval layer (hash + FAISS) |
| 7-8 | Execution engine (reuse path) |
| 9-10 | Basic API endpoints, end-to-end test |

**Acceptance Criteria:**
- Can capture and store fragments
- Can retrieve exact matches
- Can retrieve semantic matches
- Can execute reuse path
- Basic metrics available

### Phase 2: Validation (Days 11-20)

**Goal:** Full validator engine with task-type rules

| Day | Deliverable |
|-----|-------------|
| 11-12 | Validator engine core |
| 13-14 | Task-type threshold configuration |
| 15-16 | Adaptation executor (basic) |
| 17-18 | Recompute executor |
| 19-20 | Validation testing, edge cases |

**Acceptance Criteria:**
- Validator makes correct decisions
- Adaptation produces valid output
- Fallback to recompute works
- Decision logging complete

### Phase 3: Governance (Days 21-30)

**Goal:** Automated governance, variant management

| Day | Deliverable |
|-----|-------------|
| 21-22 | Decay manager |
| 23-24 | Pruning scheduler |
| 25-26 | Scoring calculator |
| 27-28 | Variant manager |
| 29-30 | Governance integration, testing |

**Acceptance Criteria:**
- Decay applies correctly
- Pruning removes correct fragments
- Scoring produces reasonable rankings
- Variants tracked and usable

### Phase 4: Polish (Days 31-35)

**Goal:** Production readiness

| Day | Deliverable |
|-----|-------------|
| 31-32 | Error handling, retries |
| 33 | Performance optimization |
| 34 | Documentation |
| 35 | Deployment preparation |

---

## 12. Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Language** | Python 3.11+ | Async support, rich ML ecosystem |
| **API Framework** | FastAPI | Modern, async, OpenAPI auto-generation |
| **Database** | PostgreSQL 15+ | Relational data, JSON support, ACID |
| **Vector DB** | FAISS | Fast similarity search, easy to deploy |
| **Cache** | Redis | Optional fast lookups for hot data |
| **ORM** | SQLAlchemy 2.0 | Type safety, async support |
| **Migrations** | Alembic | Database schema versioning |
| **Testing** | pytest + pytest-asyncio | Async test support |
| **Container** | Docker + docker-compose | Easy deployment |
| **Monitoring** | Prometheus + Grafana | Metrics collection and visualization |

---

## 13. Project Structure

```
skill_fragment_engine/
├── src/
│   ├── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # FastAPI routes
│   │   ├── schemas.py             # Request/Response Pydantic models
│   │   └── dependencies.py        # FastAPI dependencies
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py              # Domain models
│   │   ├── config.py              # Configuration management
│   │   ├── exceptions.py           # Custom exceptions
│   │   └── enums.py                # Enumerations
│   │
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── retrospector.py         # ProcessRetrospector
│   │   ├── fragmenter.py           # Fragment creation
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── base.py             # BaseExtractor
│   │       ├── code_extractor.py   # Code-specific
│   │       └── text_extractor.py   # Text-specific
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── matcher.py              # SkillMatcherLayer
│   │   ├── embedder.py             # Embedding service
│   │   ├── hasher.py               # Input hashing
│   │   └── vector_store.py         # FAISS wrapper
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── validator.py            # ValidatorEngine
│   │   ├── context_comparator.py   # Context distance
│   │   ├── decision_classifier.py  # Decision logic
│   │   └── rules/
│   │       ├── __init__.py
│   │       ├── base_rules.py       # Base rules
│   │       └── task_rules.py       # Task-specific rules
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── engine.py               # ExecutionEngine
│   │   ├── reuse_executor.py
│   │   ├── adapt_executor.py
│   │   └── recompute_executor.py
│   │
│   ├── variants/
│   │   ├── __init__.py
│   │   ├── manager.py              # VariantManager
│   │   ├── merger.py               # Variant merging
│   │   └── registry.py            # Variant tracking
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── fragment_store.py       # Main store interface
│   │   ├── postgres_repo.py        # PostgreSQL repository
│   │   ├── vector_repo.py          # Vector DB repository
│   │   └── migrations/             # Alembic migrations
│   │
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── decay_manager.py
│   │   ├── pruning_scheduler.py
│   │   ├── scoring_calculator.py
│   │   └── metrics_collector.py
│   │
│   └── services/
│       ├── __init__.py
│       ├── llm_service.py          # LLM interface
│       └── embedding_service.py    # Embedding interface
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_capture.py
│   │   ├── test_retrieval.py
│   │   ├── test_validation.py
│   │   ├── test_execution.py
│   │   └── test_governance.py
│   └── integration/
│       ├── __init__.py
│       └── test_api.py
│
├── scripts/
│   ├── init_db.py                  # Database initialization
│   ├── seed_data.py                # Test data seeding
│   └── benchmark.py                # Performance benchmarking
│
├── config/
│   ├── settings.py                 # Configuration loader
│   ├── default.yaml                # Default settings
│   └── local.yaml.example          # Local settings template
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yaml
│
├── requirements.txt
├── pyproject.toml
├── README.md
├── SPEC.md
└── CHANGELOG.md
```

---

## 14. Open Questions & Future Extensions

### 14.1 Open Questions

1. **Multi-tenancy:** Should fragments be isolated per tenant or shared?
2. **Privacy filtering:** How to ensure sensitive data is never stored?
3. **Model versioning:** How to handle when underlying LLM changes?
4. **Cross-task learning:** Can patterns from one task_type improve another?

### 14.2 Future Extensions

1. **Federated Learning:** Share patterns across organizations (privacy-preserving)
2. **Marketplace:** Buy/sell validated skill fragments
3. **AutoML:** Automatically tune thresholds based on outcomes
4. **Multi-modal:** Extend to image, audio, video tasks
5. **Distributed Cache:** Scale across multiple nodes

---

## 15. Glossary

| Term | Definition |
|------|------------|
| **Skill Fragment** | Complete record of an AI execution including input, output, patterns, and metadata |
| **Fragment Pattern** | Reusable sub-component extracted from an execution |
| **Variant** | Alternative version of a fragment created through adaptation or improvement |
| **Ritrospettiva** | Italian for "retrospective" - the process documentation aspect of capture |
| **Cognitive Cache** | A cache that understands semantics, not just keys |
| **Decay Score** | Metric indicating fragment freshness/reliability (0.0-1.0) |
| **Task Type** | Classification of the type of AI task (code_gen, summarization, etc.) |
| **Context Distance** | Semantic distance between two inputs |

---

**Document Status:** Ready for Implementation
**Last Review:** 2026-03-25
**Next Review:** After Phase 1 completion
