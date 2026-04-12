"""Recompute executor - fresh LLM execution."""

from __future__ import annotations

import time
import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.models import ExecutionRequest
from skill_fragment_engine.services.llm_service import get_llm_service, LLMService

logger = structlog.get_logger(__name__)


class RecomputeExecutor:
    """
    Executes RECOMPUTE decision.

    Performs a fresh LLM call for the request.
    This is the fallback when reuse/adapt are not viable.
    """

    def __init__(self):
        self.settings = get_settings()
        self._llm_service: LLMService | None = None
    
    @property
    def llm_service(self) -> LLMService:
        """Get or create LLM service."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    async def execute(self, request: ExecutionRequest) -> any:
        """
        Execute fresh LLM call.

        Args:
            request: Execution request

        Returns:
            LLM-generated result
        """
        start_time = time.time()

        logger.info(
            "recompute_execution",
            task_type=request.task_type,
            prompt_length=len(request.prompt),
        )

        # Build prompt for LLM
        prompt = self._build_prompt(request)

        try:
            # Call LLM service
            result = await self._call_llm(prompt, request)

            latency = time.time() - start_time
            logger.info(
                "recompute_complete",
                task_type=request.task_type,
                latency_s=round(latency, 3),
            )

            return result

        except Exception as e:
            logger.error(
                "recompute_failed",
                task_type=request.task_type,
                error=str(e),
            )
            raise

    def _build_prompt(self, request: ExecutionRequest) -> str:
        """Build prompt for LLM based on task type."""
        base_prompt = request.prompt

        # Add context if present
        if request.context:
            context_str = self._format_context(request.context)
            base_prompt = f"{base_prompt}\n\nContext:\n{context_str}"

        # Add task-specific instructions
        if request.task_type == "code_generation":
            language = request.context.get("language", "python")
            style = request.context.get("style", "clean")
            base_prompt = (
                f"Write {style} code in {language}.\n\n"
                f"{base_prompt}"
            )

        elif request.task_type == "text_summarization":
            max_length = request.parameters.get("max_length", 200)
            base_prompt = (
                f"Summarize the following text in approximately {max_length} words.\n\n"
                f"{base_prompt}"
            )

        return base_prompt

    def _format_context(self, context: dict) -> str:
        """Format context dictionary for prompt."""
        parts = []
        for key, value in context.items():
            if isinstance(value, dict):
                value_str = self._format_context(value)
            elif isinstance(value, list):
                value_str = "\n".join(f"- {v}" for v in value)
            else:
                value_str = str(value)
            parts.append(f"{key}: {value_str}")
        return "\n".join(parts)

    async def _call_llm(self, prompt: str, request: ExecutionRequest) -> any:
        """
        Call LLM service.
        
        Uses the configured LLM service (OpenAI, Anthropic, or mock).
        """
        # Get model from request context or use default
        model = request.context.get("model") if request.context else None
        temperature = request.parameters.get("temperature", 0.7) if request.parameters else 0.7
        
        # Call the LLM service
        response = await self.llm_service.complete(
            prompt=prompt,
            model=model,
            temperature=temperature,
        )
        
        # Return structured result
        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider.value,
            "usage": response.usage,
            "task_type": request.task_type,
        }

    def estimate_cost(self) -> float:
        """Estimate cost for recompute."""
        return self.settings.base_execution_cost
