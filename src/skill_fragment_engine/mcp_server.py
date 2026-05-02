"""MCP Server for Skill Fragment Engine."""

import json
import os
import hmac
from typing import Any
from datetime import datetime

from skill_fragment_engine.core.enums import TaskType, FeedbackType, FeedbackCategory
from skill_fragment_engine.core.models import ExecutionRequest, UserFeedback, SkillFragment
from skill_fragment_engine.execution.engine import ExecutionEngine
from skill_fragment_engine.retrieval.matcher import SkillMatcherLayer
from skill_fragment_engine.retrieval.clustering import ClusteringService
from skill_fragment_engine.store import FragmentStore
from skill_fragment_engine.retrieval.vector_store import VectorStore
from skill_fragment_engine.retrieval.embedder import EmbeddingService
from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.metrics import metrics_collector
from skill_fragment_engine.services.feedback_service import get_feedback_service
from skill_fragment_engine.services.versioning_service import get_versioning_service
from skill_fragment_engine.services.rollback_service import get_rollback_service
from skill_fragment_engine.services.transfer_learning_service import get_transfer_learning_service


API_KEY = os.environ.get("SFE_API_KEY", "")
_api_key_verified = False


def verify_api_key(key: str) -> bool:
    """Verify API key."""
    global _api_key_verified
    if not API_KEY:
        _api_key_verified = True
        return True
    if hmac.compare_digest(key, API_KEY):
        _api_key_verified = True
        return True
    return False


def require_auth(func):
    """Decorator to require API key authentication."""
    async def wrapper(*args, **kwargs):
        if API_KEY and not _api_key_verified:
            raise PermissionError("API key required")
        return await func(*args, **kwargs)
    return wrapper


class MCPServer:
    """MCP Server exposing SFE as tools for AI agents."""

    def __init__(self):
        self.engine = ExecutionEngine()
        self.matcher = SkillMatcherLayer()
        self.settings = get_settings()

    async def execute_task(
        self,
        prompt: str,
        task_type: str = "code_generation",
        context: dict | None = None,
        parameters: dict | None = None,
    ) -> dict:
        """
        Execute a task through SFE pipeline.
        
        Args:
            prompt: The task prompt/query
            task_type: Type of task (code_generation, code_review, refactoring, etc.)
            context: Additional context for execution
            parameters: Execution parameters
        """
        request = ExecutionRequest(
            task_type=TaskType(task_type),
            prompt=prompt,
            context=context or {},
            parameters=parameters or {},
        )
        response = await self.engine.execute(request)
        
        return {
            "execution_id": str(response.execution_id),
            "decision": response.decision,
            "result": response.result,
            "fragment_id": str(response.metadata.fragment_id) if response.metadata.fragment_id else None,
            "cost": response.metadata.cost,
            "latency_ms": response.metadata.latency_ms,
        }

    async def search_fragments(
        self,
        query: str,
        task_type: str = "code_generation",
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Search for similar cached fragments."""
        candidates = await self.matcher.find_candidates(
            prompt=query,
            task_type=TaskType(task_type),
            top_k=top_k,
        )
        
        return [
            {
                "fragment_id": str(c.fragment_id),
                "score": c.score,
            }
            for c in candidates
            if c.score >= min_score
        ]

    async def submit_feedback(
        self,
        feedback_type: str,
        score: float,
        fragment_id: str | None = None,
        execution_id: str | None = None,
        category: str = "quality",
        comment: str | None = None,
    ) -> dict:
        """Submit feedback on a fragment execution."""
        feedback = UserFeedback(
            feedback_id=None,
            execution_id=execution_id,
            fragment_id=fragment_id,
            variant_id=None,
            feedback_type=FeedbackType(feedback_type),
            category=FeedbackCategory(category),
            score=score,
            comment=comment,
            expected_output=None,
            actual_output=None,
            user_id=None,
            session_id=None,
        )
        
        feedback_svc = get_feedback_service()
        stored = await feedback_svc.add_feedback(feedback)
        
        return {
            "feedback_id": str(stored.feedback_id),
            "success": True,
        }

    async def get_metrics(self) -> dict:
        """Get system-wide metrics."""
        metrics = metrics_collector.get_metrics()
        
        total_requests = metrics["total_requests"]
        if total_requests > 0:
            reuse_count = metrics["reuse_count"]
            adapt_count = metrics["adapt_count"]
            recompute_count = metrics["recompute_count"]
            total_cost = (reuse_count * 0.000002) + (adapt_count * 0.0021) + (recompute_count * 0.021)
            avg_cost = total_cost / total_requests
        else:
            avg_cost = 0.0
        
        return {
            "total_fragments": metrics["active_fragments"],
            "reuse_rate": metrics["reuse_rate"],
            "avg_cost_per_request": avg_cost,
            "latency_p50_ms": metrics["latency_p50_ms"],
            "latency_p99_ms": metrics["latency_p99_ms"],
        }

    async def get_fragment_versions(
        self,
        fragment_id: str,
        include_deprecated: bool = False,
    ) -> list[dict]:
        """Get version history for a fragment."""
        versioning_svc = get_versioning_service()
        return versioning_svc.get_version_history(fragment_id, include_deprecated)

    async def rollback_to_version(
        self,
        fragment_id: str,
        version_number: int,
        reason: str = "",
    ) -> dict:
        """Rollback to a specific version."""
        versioning_svc = get_versioning_service()
        version = versioning_svc.rollback_to_version(
            fragment_id=fragment_id,
            version_number=version_number,
            reason=reason,
        )
        
        return {
            "success": True,
            "rollback_to_version": version_number,
            "new_version": version.version_number,
        }

    async def get_rollback_stats(self) -> dict:
        """Get rollback statistics."""
        rollback_svc = get_rollback_service()
        return rollback_svc.get_rollback_stats()

    async def get_transfer_learning_stats(
        self,
        task_type: str | None = None,
    ) -> dict:
        """Get transfer learning pattern statistics."""
        tl_svc = get_transfer_learning_service()
        return tl_svc.get_pattern_stats(task_type)

    async def suggest_adaptation(
        self,
        task_type: str,
        original_parameters: dict,
        context: dict,
    ) -> dict:
        """Get suggested adaptation parameters."""
        tl_svc = get_transfer_learning_service()
        return await tl_svc.suggest_adaptation(task_type, original_parameters, context)

    async def run_clustering(
        self,
        task_type: str | None = None,
        method: str = "auto",
    ) -> dict:
        """Run clustering on fragments."""
        vector_store = VectorStore()
        fragment_store = FragmentStore()
        
        if fragment_store.count() == 0:
            return {"message": "No fragments to cluster", "clusters": []}
        
        embeddings = {}
        fragment_ids = []
        
        for fid in fragment_store._data.keys():
            rec = fragment_store._data[fid]
            if task_type and rec.get("task_type") != task_type:
                continue
            
            frag_raw = rec.get("fragment")
            if not frag_raw:
                continue
            
            embedding = vector_store.get(fid)
            if embedding:
                embeddings[fid] = embedding
                fragment_ids.append(fid)
        
        if not embeddings:
            return {"message": "No embeddings found", "clusters": []}
        
        clustering_svc = ClusteringService(method=method)
        cluster_mapping = clustering_svc.cluster_fragments(embeddings, method)
        
        n_clusters = len(set(cluster_mapping.values()))
        
        return {
            "n_fragments": len(cluster_mapping),
            "n_clusters": n_clusters,
            "method": method,
            "cluster_mapping": cluster_mapping,
        }

    async def get_health(self) -> dict:
        """Get system health status."""
        return {
            "status": "healthy",
            "version": self.settings.app_version,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def save_trace(
        self,
        prompt: str,
        result: str,
        task_type: str = "code_generation",
        context: dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Save a cognitive trace (fragment) to SFE from external source.
        
        Allows an external agent to save execution traces without going through execute().
        
        Args:
            prompt: The original task prompt
            result: The execution result/output
            task_type: Type of task
            context: Additional context
            metadata: Additional metadata
        """
        from uuid import uuid4
        
        fragment = SkillFragment(
            fragment_id=uuid4(),
            task_type=TaskType(task_type),
            prompt=prompt,
            result=result,
            context=context or {},
            metadata=metadata or {},
            quality_score=1.0,
            decay_score=1.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        fragment_store = FragmentStore()
        fragment_store.add(fragment)
        
        vector_store = VectorStore()
        embedder = EmbeddingService()
        embedding = embedder.embed(prompt)
        vector_store.add(str(fragment.fragment_id), embedding)
        
        return {
            "fragment_id": str(fragment.fragment_id),
            "success": True,
            "message": "Cognitive trace saved successfully",
        }


_mcp_server = None


def get_mcp_server() -> MCPServer:
    """Get MCP server instance."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server


TOOL_DEFINITIONS = [
    {
        "name": "sfe_execute",
        "description": "Execute a task through Skill Fragment Engine. The system will search for similar cached fragments, validate if a fragment can be reused, and either reuse cached result, adapt it, or compute fresh.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The task prompt/query"},
                "task_type": {"type": "string", "description": "Type of task", "default": "code_generation"},
                "context": {"type": "object", "description": "Additional context"},
                "parameters": {"type": "object", "description": "Execution parameters"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "sfe_search",
        "description": "Search for similar cached fragments in SFE. Returns fragments ranked by similarity to the query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "task_type": {"type": "string", "description": "Type of task", "default": "code_generation"},
                "top_k": {"type": "integer", "description": "Maximum results", "default": 5},
                "min_score": {"type": "number", "description": "Minimum similarity score", "default": 0.5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "sfe_feedback",
        "description": "Submit feedback on a fragment execution. Used to improve fragment quality scores and decision thresholds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "feedback_type": {"type": "string", "description": "positive, negative, or neutral"},
                "score": {"type": "number", "description": "Quality score from 0 to 1"},
                "fragment_id": {"type": "string", "description": "Related fragment ID"},
                "execution_id": {"type": "string", "description": "Related execution ID"},
                "category": {"type": "string", "description": "Category", "default": "quality"},
                "comment": {"type": "string", "description": "Optional comment"},
            },
            "required": ["feedback_type", "score"],
        },
    },
    {
        "name": "sfe_metrics",
        "description": "Get system-wide performance metrics including reuse rate, latency, and costs.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "sfe_versions",
        "description": "Get version history for a fragment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fragment_id": {"type": "string", "description": "Fragment ID"},
                "include_deprecated": {"type": "boolean", "description": "Include deprecated versions", "default": False},
            },
            "required": ["fragment_id"],
        },
    },
    {
        "name": "sfe_rollback",
        "description": "Rollback a fragment to a specific version.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fragment_id": {"type": "string", "description": "Fragment ID"},
                "version_number": {"type": "integer", "description": "Version to rollback to"},
                "reason": {"type": "string", "description": "Reason for rollback"},
            },
            "required": ["fragment_id", "version_number"],
        },
    },
    {
        "name": "sfe_rollback_stats",
        "description": "Get rollback statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "sfe_transfer_learning_stats",
        "description": "Get transfer learning pattern statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "Filter by task type"},
            },
        },
    },
    {
        "name": "sfe_suggest_adaptation",
        "description": "Get suggested adaptation parameters based on learned patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "Task type"},
                "original_parameters": {"type": "object", "description": "Original parameters"},
                "context": {"type": "object", "description": "Context"},
            },
            "required": ["task_type", "original_parameters", "context"],
        },
    },
    {
        "name": "sfe_cluster",
        "description": "Run clustering on stored fragments to group similar ones together.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "description": "Filter by task type"},
                "method": {"type": "string", "description": "Clustering method (auto, kmeans, dbscan, hierarchical)", "default": "auto"},
            },
        },
    },
    {
        "name": "sfe_health",
        "description": "Get system health status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "sfe_save_trace",
        "description": "Save a cognitive trace (fragment) to SFE from an external agent. Allows saving execution results without going through execute(). Useful for agents that computed results independently and want to cache them.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The original task prompt"},
                "result": {"type": "string", "description": "The execution result/output"},
                "task_type": {"type": "string", "description": "Type of task", "default": "code_generation"},
                "context": {"type": "object", "description": "Additional context"},
                "metadata": {"type": "object", "description": "Additional metadata"},
            },
            "required": ["prompt", "result"],
        },
    },
]


async def handle_tool_call(tool_name: str, arguments: dict, api_key: str = "") -> dict:
    """Handle MCP tool call."""
    if API_KEY and not verify_api_key(api_key):
        return {"error": "Invalid API key"}
    
    server = get_mcp_server()
    
    handlers = {
        "sfe_execute": server.execute_task,
        "sfe_search": server.search_fragments,
        "sfe_feedback": server.submit_feedback,
        "sfe_metrics": server.get_metrics,
        "sfe_versions": server.get_fragment_versions,
        "sfe_rollback": server.rollback_to_version,
        "sfe_rollback_stats": server.get_rollback_stats,
        "sfe_transfer_learning_stats": server.get_transfer_learning_stats,
        "sfe_suggest_adaptation": server.suggest_adaptation,
        "sfe_cluster": server.run_clustering,
        "sfe_health": server.get_health,
        "sfe_save_trace": server.save_trace,
    }
    
    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    
    try:
        result = await handler(**arguments)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}