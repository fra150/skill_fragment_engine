"""LLM service for making API calls to language models."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import structlog

from skill_fragment_engine.core.config import get_settings
from skill_fragment_engine.core.exceptions import ExecutionError

logger = structlog.get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class LLMResponse:
    """Response from LLM API."""
    
    def __init__(
        self,
        content: str,
        model: str,
        provider: LLMProvider,
        usage: dict[str, int] | None = None,
        raw_response: dict | None = None,
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.usage = usage or {}
        self.raw_response = raw_response or {}
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.usage.get("total_tokens", 0)
    
    @property
    def prompt_tokens(self) -> int:
        """Prompt tokens used."""
        return self.usage.get("prompt_tokens", 0)
    
    @property
    def completion_tokens(self) -> int:
        """Completion tokens used."""
        return self.usage.get("completion_tokens", 0)


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a completion."""
        pass


class OpenAIBackend(LLMBackend):
    """OpenAI API backend."""
    
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
    
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        import aiohttp
        
        model = model or "gpt-4"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=get_settings().llm_timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ExecutionError(f"OpenAI API error: {response.status} - {error_text}")
                
                data = await response.json()
                
                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data["model"],
                    provider=LLMProvider.OPENAI,
                    usage={
                        "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                        "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                        "total_tokens": data.get("usage", {}).get("total_tokens", 0),
                    },
                    raw_response=data,
                )


class AnthropicBackend(LLMBackend):
    """Anthropic API backend."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
    
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate completion using Anthropic API."""
        import aiohttp
        
        model = model or "claude-3-sonnet-20240229"
        
        headers = {
            "x-api-key": self.api_key or "",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        
        payload.update(kwargs)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=get_settings().llm_timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ExecutionError(f"Anthropic API error: {response.status} - {error_text}")
                
                data = await response.json()
                
                return LLMResponse(
                    content=data["content"][0]["text"],
                    model=data["model"],
                    provider=LLMProvider.ANTHROPIC,
                    usage={
                        "input_tokens": data.get("usage", {}).get("input_tokens", 0),
                        "output_tokens": data.get("usage", {}).get("output_tokens", 0),
                        "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
                    },
                    raw_response=data,
                )


class MockBackend(LLMBackend):
    """Mock backend for testing."""
    
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Return mock response."""
        logger.warning("llm_call_mocked", prompt=prompt[:100])
        
        return LLMResponse(
            content=f"Mock response for: {prompt[:50]}...",
            model=model or "mock",
            provider=LLMProvider.MOCK,
            usage={"total_tokens": 10},
            raw_response={},
        )


class LLMService:
    """
    LLM service with retry logic and provider switching.
    
    Supports OpenAI, Anthropic, and mock backends.
    """
    
    def __init__(
        self,
        provider: LLMProvider | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        settings = get_settings()
        
        model_prefix = settings.llm_model.split("-")[0].lower()
        if "gpt" in model_prefix:
            mapped_provider = "openai"
        elif "claude" in model_prefix:
            mapped_provider = "anthropic"
        else:
            mapped_provider = model_prefix
        self.provider = provider or LLMProvider(mapped_provider)
        self.api_key = api_key or settings.llm_api_key or "mock-key"
        self.base_url = base_url or settings.llm_base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self._backend = self._create_backend()
    
    def _create_backend(self) -> LLMBackend:
        """Create the appropriate backend based on provider."""
        
        if self.provider == LLMProvider.OPENAI:
            return OpenAIBackend(self.api_key, self.base_url)
        elif self.provider == LLMProvider.ANTHROPIC:
            return AnthropicBackend(self.api_key)
        else:
            return MockBackend()
    
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion with retry logic.
        
        Args:
            prompt: The prompt to send to the LLM
            model: Model to use (overrides default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with the generated content
        """
        last_error: Exception | None = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    "llm_request",
                    provider=self.provider.value,
                    model=model or "default",
                    attempt=attempt + 1,
                    prompt_length=len(prompt),
                )
                
                start_time = time.time()
                response = await self._backend.complete(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                latency = time.time() - start_time
                
                logger.info(
                    "llm_response",
                    provider=self.provider.value,
                    model=response.model,
                    latency_s=round(latency, 3),
                    tokens=response.total_tokens,
                )
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_request_failed",
                    provider=self.provider.value,
                    attempt=attempt + 1,
                    error=str(e),
                )
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info("llm_retry_delay", delay_s=delay)
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        raise ExecutionError(
            f"LLM request failed after {self.max_retries} attempts: {last_error}"
        )
    
    async def complete_with_json(
        self,
        prompt: str,
        response_schema: dict | None = None,
        **kwargs,
    ) -> dict:
        """
        Generate completion expecting JSON response.
        
        Args:
            prompt: The prompt to send
            response_schema: JSON schema for the response (if supported)
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON response
        """
        import json
        
        # Add JSON formatting instruction to prompt
        json_prompt = f"""{prompt}

Respond only with valid JSON, no additional text or explanation.
"""
        
        response = await self.complete(json_prompt, **kwargs)
        
        try:
            # Try to parse as JSON
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            content = response.content
            # Find first { and last }
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start:end+1])
                except json.JSONDecodeError:
                    pass
            
            raise ExecutionError(f"Failed to parse JSON response: {response.content[:200]}")


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        settings = get_settings()
        provider = LLMProvider.MOCK if not settings.llm_api_key else None
        _llm_service = LLMService(provider=provider)
    return _llm_service