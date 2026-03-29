Da aggiugere 

"""
Skill Fragment Engine — Execution Engine

Core principle: LOOK BEFORE YOU THINK.
The AI reads past cognitive traces before starting any new task.
"""

from dataclasses import dataclass
from typing import Optional
from store import FragmentStore
from models import Fragment, build_fragment_from_execution


@dataclass
class ExecutionRequest:
    task_type: str
    prompt: str
    context: dict = None


@dataclass
class ExecutionResponse:
    output: str
    decision: str           # REUSE | ADAPT | RECOMPUTE
    tokens_used: int
    tokens_saved: int
    fragment_id: str
    source_fragment_id: Optional[str] = None  # if reused/adapted


class ExecutionEngine:
    """
    The engine that never repeats itself.
    
    Before ANY execution:
    1. Check exact match     → free
    2. Check similar matches → free  
    3. Inject findings into context
    4. Execute with full cognitive history available
    5. Save the new cognitive trace
    """

    def __init__(self, llm_caller=None):
        self.store = FragmentStore()
        self.llm_caller = llm_caller  # inject your LLM function here

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        print(f"\n{'='*60}")
        print(f"[ENGINE] New task: {request.task_type}")
        print(f"[ENGINE] Prompt: {request.prompt[:80]}...")

        # ─── STEP 1: EXACT MATCH (0 tokens) ───────────────────────
        exact = self.store.lookup_exact(request.prompt, request.task_type)
        if exact and exact.decay_score > 0.5:
            print(f"[ENGINE] REUSE — returning cached result, 0 tokens spent")
            exact.total_tokens_saved += exact.creation_cost_tokens
            self.store.save(exact)
            return ExecutionResponse(
                output=exact.trace.output,
                decision="REUSE",
                tokens_used=0,
                tokens_saved=exact.creation_cost_tokens,
                fragment_id=exact.fragment_id,
                source_fragment_id=exact.fragment_id,
            )

        # ─── STEP 2: SIMILAR MATCH (0 tokens) ─────────────────────
        similar = self.store.lookup_similar(request.prompt, request.task_type)

        # ─── STEP 3: BUILD CONTEXT WITH PAST KNOWLEDGE ────────────
        injected_context = self._build_context(request, similar)

        # ─── STEP 4: EXECUTE (with cognitive history as context) ───
        print(f"[ENGINE] {'ADAPT' if similar else 'RECOMPUTE'} — calling LLM")
        print(f"[ENGINE] Injecting {len(similar)} past fragment(s) as context")

        result = self._call_llm(request, injected_context)

        # ─── STEP 5: SAVE COGNITIVE TRACE ─────────────────────────
        fragment = build_fragment_from_execution(
            task_type=request.task_type,
            prompt=request.prompt,
            context=request.context or {},
            thinking=result.get("thinking", ""),
            tool_sequence=result.get("tool_sequence", []),
            errors=result.get("errors", []),
            recovery=result.get("recovery", []),
            rejected=result.get("rejected_approaches", []),
            dependencies=result.get("discovered_dependencies", []),
            relevant_context=result.get("relevant_context_used", []),
            output=result.get("output", ""),
            tokens_used=result.get("tokens_used", 0),
        )
        self.store.save(fragment)

        decision = "ADAPT" if similar else "RECOMPUTE"
        tokens_saved = sum(s.creation_cost_tokens for s in similar) if similar else 0

        print(f"[ENGINE] Done. Decision={decision}, tokens_used={result.get('tokens_used')}, "
              f"tokens_saved_vs_cold={tokens_saved}")

        return ExecutionResponse(
            output=result.get("output", ""),
            decision=decision,
            tokens_used=result.get("tokens_used", 0),
            tokens_saved=tokens_saved,
            fragment_id=fragment.fragment_id,
            source_fragment_id=similar[0].fragment_id if similar else None,
        )

    def _build_context(self, request: ExecutionRequest, similar: list[Fragment]) -> str:
        """
        Assembles the cognitive history block injected before any LLM call.
        This is what makes the AI "remember" without re-spending tokens.
        """
        if not similar:
            return ""

        blocks = []
        for frag in similar:
            blocks.append(frag.to_context_injection())

        header = (
            f"COGNITIVE HISTORY — {len(similar)} relevant past execution(s) found.\n"
            f"Read these before starting. Use them to avoid repeating work.\n\n"
        )
        return header + "\n\n".join(blocks)

    def _call_llm(self, request: ExecutionRequest, injected_context: str) -> dict:
        """
        Calls the LLM with past cognitive context pre-loaded.
        Replace this with your actual LLM integration.
        
        The injected_context goes into the system prompt — not the user message.
        This means the AI "knows" its history before even reading the task.
        """
        if self.llm_caller:
            return self.llm_caller(
                task_type=request.task_type,
                prompt=request.prompt,
                context=request.context,
                cognitive_history=injected_context,
            )

        # Stub for testing without LLM
        print("[ENGINE] (stub mode — no real LLM connected)")
        return {
            "thinking": "Analyzed the request...",
            "tool_sequence": [],
            "errors": [],
            "recovery": [],
            "rejected_approaches": [],
            "discovered_dependencies": [],
            "relevant_context_used": [],
            "output": f"[STUB OUTPUT for: {request.prompt[:50]}]",
            "tokens_used": 150,
        }

    def stats(self):
        s = self.store.stats()
        print(f"\n[STATS] {s}")
        return s


# ──────────────────────────────────────────────────────────────
# Quick test
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = ExecutionEngine()

    # First execution — RECOMPUTE (nothing in store)
    r1 = engine.execute(ExecutionRequest(
        task_type="code_generation",
        prompt="Write a function to reverse a string in Python",
    ))
    print(f"\nResult 1: decision={r1.decision}, tokens={r1.tokens_used}")

    # Same execution — REUSE (exact match)
    r2 = engine.execute(ExecutionRequest(
        task_type="code_generation",
        prompt="Write a function to reverse a string in Python",
    ))
    print(f"\nResult 2: decision={r2.decision}, tokens={r2.tokens_used}, saved={r2.tokens_saved}")

    # Similar execution — ADAPT (similar match)
    r3 = engine.execute(ExecutionRequest(
        task_type="code_generation",
        prompt="Write a function to reverse a list in Python",
    ))
    print(f"\nResult 3: decision={r3.decision}, tokens={r3.tokens_used}")

    engine.stats() 


    --------------------------------------------------

    """
Skill Fragment Engine — Core Models
Every AI execution leaves a cognitive trace. This is that trace.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4
import hashlib
import json


@dataclass
class CognitiveTrace:
    """
    Everything the AI did, thought, and decided during one execution.
    This is the reusable unit — not just the output, but the entire reasoning path.
    """

    # --- WHAT IT THOUGHT ---
    thinking: str                        # The AI's reasoning before acting
    rejected_approaches: list[str]       # Paths considered but discarded (and why)

    # --- WHAT IT DID ---
    tool_sequence: list[dict]            # Tools used, in order, with inputs/outputs
    # Example:
    # [
    #   {"tool": "read_file", "input": "main.py", "output": "...content..."},
    #   {"tool": "bash", "input": "pytest", "output": "3 passed"},
    # ]

    # --- WHAT WENT WRONG ---
    errors_encountered: list[dict]       # Errors hit during execution
    recovery_actions: list[str]          # How each error was resolved

    # --- WHAT IT LEARNED ---
    relevant_context_used: list[str]     # Which parts of context actually mattered
    discovered_dependencies: list[str]   # "To do X, I needed Y (wasn't obvious from input)"

    # --- THE RESULT ---
    output: str                          # Final output


@dataclass
class Fragment:
    """
    A complete, reusable unit of AI knowledge.
    Contains input signature + full cognitive trace + reuse metadata.
    """

    # Identity
    fragment_id: str = field(default_factory=lambda: str(uuid4()))
    task_type: str = ""                  # code_generation | text_summarization | etc.

    # Input fingerprint
    input_raw: str = ""                  # Original prompt
    input_hash: str = ""                 # SHA256 of normalized input (for exact match)
    context_snapshot: dict = field(default_factory=dict)  # Relevant context at execution time

    # The cognitive trace
    trace: Optional[CognitiveTrace] = None

    # Reuse metadata
    reuse_count: int = 0
    adapt_count: int = 0
    failure_count: int = 0
    decay_score: float = 1.0             # 1.0 = fresh, 0.0 = stale
    quality_score: float = 0.0           # Set by judge after execution

    # Cost tracking
    creation_cost_tokens: int = 0
    total_tokens_saved: int = 0

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used_at: Optional[str] = None

    def to_context_injection(self) -> str:
        """
        Formats this fragment as a context block to inject into the AI's prompt.
        This is what the AI reads BEFORE starting a new task.
        Zero LLM tokens to generate — just a dict read + format.
        """
        if not self.trace:
            return ""

        return f"""
=== FRAGMENT FROM PREVIOUS EXECUTION (reused {self.reuse_count}x) ===

TASK TYPE: {self.task_type}
ORIGINAL INPUT: {self.input_raw[:200]}...

HOW I REASONED:
{self.trace.thinking}

TOOLS I USED (in order):
{self._format_tool_sequence()}

APPROACHES I REJECTED:
{chr(10).join(f"- {r}" for r in self.trace.rejected_approaches)}

ERRORS I HIT AND HOW I FIXED THEM:
{self._format_errors()}

WHAT I DISCOVERED ALONG THE WAY:
{chr(10).join(f"- {d}" for d in self.trace.discovered_dependencies)}

THE OUTPUT:
{self.trace.output[:500]}...

DECAY SCORE: {self.decay_score:.2f} (1.0 = fresh)
QUALITY SCORE: {self.quality_score:.2f}

=== END FRAGMENT ===

Based on the above, decide:
- REUSE: if current task is essentially the same
- ADAPT: if the reasoning path applies but output needs adjustment  
- RECOMPUTE: if this fragment is not relevant
"""

    def _format_tool_sequence(self) -> str:
        if not self.trace or not self.trace.tool_sequence:
            return "none"
        lines = []
        for i, step in enumerate(self.trace.tool_sequence, 1):
            lines.append(f"  {i}. {step.get('tool')} → {str(step.get('output', ''))[:80]}")
        return "\n".join(lines)

    def _format_errors(self) -> str:
        if not self.trace or not self.trace.errors_encountered:
            return "none"
        lines = []
        for err in self.trace.errors_encountered:
            lines.append(f"  ERROR: {err.get('error')} → FIX: {err.get('fix')}")
        return "\n".join(lines)


def compute_input_hash(prompt: str, task_type: str) -> str:
    """Deterministic hash for exact-match lookup. No LLM involved."""
    normalized = f"{task_type}::{prompt.lower().strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def build_fragment_from_execution(
    task_type: str,
    prompt: str,
    context: dict,
    thinking: str,
    tool_sequence: list[dict],
    errors: list[dict],
    recovery: list[str],
    rejected: list[str],
    dependencies: list[str],
    relevant_context: list[str],
    output: str,
    tokens_used: int,
) -> Fragment:
    """
    Factory: builds a Fragment from a completed execution.
    Call this at the END of every task to persist the cognitive trace.
    """
    trace = CognitiveTrace(
        thinking=thinking,
        rejected_approaches=rejected,
        tool_sequence=tool_sequence,
        errors_encountered=errors,
        recovery_actions=recovery,
        relevant_context_used=relevant_context,
        discovered_dependencies=dependencies,
        output=output,
    )

    return Fragment(
        task_type=task_type,
        input_raw=prompt,
        input_hash=compute_input_hash(prompt, task_type),
        context_snapshot=context,
        trace=trace,
        creation_cost_tokens=tokens_used,
    ) 

    ------------------------------------------------------
    """
Skill Fragment Engine — Store + Lookup

The AI reads this BEFORE starting any task.
No LLM call during lookup — pure data retrieval.
"""

import json
import os
from datetime import datetime
from typing import Optional
from models import Fragment, compute_input_hash


STORE_PATH = "fragments.json"


class FragmentStore:
    """
    Lightweight JSON store for fragments.
    Phase 1: JSON file (zero dependencies)
    Phase 2: PostgreSQL + FAISS (when volume justifies it)
    """

    def __init__(self, path: str = STORE_PATH):
        self.path = path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                self._data = json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    def save(self, fragment: Fragment):
        """Persist a fragment after execution."""
        import dataclasses
        d = dataclasses.asdict(fragment) if dataclasses.is_dataclass(fragment) else fragment.__dict__
        self._data[fragment.fragment_id] = d
        self._save()
        print(f"[STORE] Fragment saved: {fragment.fragment_id[:8]}... "
              f"(task={fragment.task_type}, tokens_cost={fragment.creation_cost_tokens})")

    def lookup_exact(self, prompt: str, task_type: str) -> Optional[Fragment]:
        """
        Exact hash match — ZERO cost.
        Same prompt + same task_type → return immediately.
        """
        target_hash = compute_input_hash(prompt, task_type)

        for frag_dict in self._data.values():
            if frag_dict.get("input_hash") == target_hash:
                frag = self._deserialize(frag_dict)
                frag.reuse_count += 1
                frag.last_used_at = datetime.utcnow().isoformat()
                self.save(frag)
                print(f"[LOOKUP] ✅ EXACT match — 0 tokens spent")
                return frag

        return None

    def lookup_similar(self, prompt: str, task_type: str, top_k: int = 3) -> list[Fragment]:
        """
        Keyword-based similarity — still ZERO LLM tokens.
        Phase 2 will replace this with embedding similarity.
        
        Returns up to top_k fragments that share keywords with the prompt.
        """
        prompt_words = set(prompt.lower().split())
        candidates = []

        for frag_dict in self._data.values():
            if frag_dict.get("task_type") != task_type:
                continue

            # Skip exact matches (already handled)
            if frag_dict.get("input_hash") == compute_input_hash(prompt, task_type):
                continue

            # Simple keyword overlap score
            frag_words = set(frag_dict.get("input_raw", "").lower().split())
            overlap = len(prompt_words & frag_words) / max(len(prompt_words), 1)

            if overlap > 0.3:  # at least 30% keyword overlap
                candidates.append((overlap, frag_dict))

        # Sort by overlap score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, frag_dict in candidates[:top_k]:
            frag = self._deserialize(frag_dict)
            print(f"[LOOKUP] 🔍 Similar fragment found (overlap={score:.0%}): "
                  f"{frag.input_raw[:60]}...")
            results.append(frag)

        return results

    def get_all_by_type(self, task_type: str) -> list[Fragment]:
        return [
            self._deserialize(d)
            for d in self._data.values()
            if d.get("task_type") == task_type
        ]

    def _deserialize(self, d: dict) -> Fragment:
        """Reconstruct a Fragment from stored dict."""
        from models import CognitiveTrace
        frag = Fragment.__new__(Fragment)
        frag.__dict__.update(d)
        
        # Reconstruct CognitiveTrace if present
        trace_raw = d.get("trace")
        if isinstance(trace_raw, dict) and trace_raw:
            trace_data = trace_raw
            frag.trace = CognitiveTrace(
                thinking=trace_data.get("thinking", ""),
                rejected_approaches=trace_data.get("rejected_approaches", []),
                tool_sequence=trace_data.get("tool_sequence", []),
                errors_encountered=trace_data.get("errors_encountered", []),
                recovery_actions=trace_data.get("recovery_actions", []),
                relevant_context_used=trace_data.get("relevant_context_used", []),
                discovered_dependencies=trace_data.get("discovered_dependencies", []),
                output=trace_data.get("output", ""),
            )
        else:
            frag.trace = None

        return frag

    def stats(self) -> dict:
        """Quick health check — what's in the store."""
        total = len(self._data)
        total_saved = sum(
            d.get("total_tokens_saved", 0) for d in self._data.values()
        )
        by_type = {}
        for d in self._data.values():
            t = d.get("task_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_fragments": total,
            "total_tokens_saved": total_saved,
            "by_task_type": by_type,
        }