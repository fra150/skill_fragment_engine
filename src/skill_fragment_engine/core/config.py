"""Configuration management for SFE."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# =============================================================================
# Task Type Thresholds
# =============================================================================


class TaskTypeThresholds(BaseModel):
    """Thresholds for a specific task type."""

    exact_match: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Max distance for exact match"
    )
    adapt_match: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Max distance for adaptation"
    )
    adaptation_allowed: bool = Field(
        default=True,
        description="Whether adaptation is allowed for this type"
    )
    half_life_days: int = Field(
        default=90,
        ge=1,
        description="Decay half-life in days"
    )
    min_decay_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum decay score before deactivation"
    )


THRESHOLDS_CONFIG: dict[str, TaskTypeThresholds] = {
    "code_generation": TaskTypeThresholds(
        exact_match=0.05,
        adapt_match=0.15,
        adaptation_allowed=True,
        half_life_days=90,
        min_decay_threshold=0.5,
    ),
    "text_summarization": TaskTypeThresholds(
        exact_match=0.08,
        adapt_match=0.20,
        adaptation_allowed=True,
        half_life_days=30,
        min_decay_threshold=0.6,
    ),
    "data_extraction": TaskTypeThresholds(
        exact_match=0.03,
        adapt_match=0.10,
        adaptation_allowed=False,
        half_life_days=180,
        min_decay_threshold=0.7,
    ),
    "classification": TaskTypeThresholds(
        exact_match=0.01,
        adapt_match=0.05,
        adaptation_allowed=False,
        half_life_days=60,
        min_decay_threshold=0.55,
    ),
    "translation": TaskTypeThresholds(
        exact_match=0.02,
        adapt_match=0.05,
        adaptation_allowed=True,
        half_life_days=45,
        min_decay_threshold=0.5,
    ),
    "question_answering": TaskTypeThresholds(
        exact_match=0.08,
        adapt_match=0.25,
        adaptation_allowed=True,
        half_life_days=30,
        min_decay_threshold=0.6,
    ),
}


# =============================================================================
# Main Settings
# =============================================================================


class Settings(BaseSettings):
    """Application settings."""

    # App
    app_name: str = "Skill Fragment Engine"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False)

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/sfe",
        description="PostgreSQL connection URL"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Vector Store (FAISS)
    vector_store_path: str = Field(
        default="./data/faiss",
        description="Path to FAISS index"
    )
    fragment_store_path: str = Field(
        default="./data/fragments.json",
        description="Path to fragment JSON store"
    )
    embedding_dim: int = Field(
        default=1536,
        description="Embedding dimension"
    )
    embedding_model: str = Field(
        default="text-embedding-ada-002",
        description="OpenAI embedding model"
    )

    # Redis (optional cache)
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL"
    )
    redis_enabled: bool = Field(
        default=False,
        description="Enable Redis caching"
    )

    # LLM Service
    llm_api_key: str | None = Field(
        default=None,
        description="LLM API key"
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="LLM API base URL"
    )
    llm_model: str = Field(
        default="gpt-4",
        description="Default LLM model"
    )
    llm_timeout: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="LLM timeout in seconds"
    )

    # Retrieval
    similarity_top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of similar fragments to retrieve"
    )
    min_similarity_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score to consider"
    )
    keyword_similarity_min_overlap: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum keyword overlap to consider a similar match"
    )

    # Governance
    decay_enabled: bool = Field(
        default=True,
        description="Enable decay management"
    )
    pruning_enabled: bool = Field(
        default=True,
        description="Enable automatic pruning"
    )
    pruning_schedule: str = Field(
        default="0 2 * * *",  # Daily at 2 AM
        description="Cron schedule for pruning"
    )
    decay_schedule: str = Field(
        default="0 3 * * *",  # Daily at 3 AM
        description="Cron schedule for decay calculation"
    )

    # Cost Model
    base_execution_cost: float = Field(
        default=0.021,
        ge=0.0,
        description="Baseline cost for new execution ($)"
    )
    reuse_cost: float = Field(
        default=0.000002,
        ge=0.0,
        description="Cost for exact reuse ($)"
    )
    semantic_reuse_cost: float = Field(
        default=0.00011,
        ge=0.0,
        description="Cost for semantic reuse ($)"
    )
    adaptation_cost: float = Field(
        default=0.0021,
        ge=0.0,
        description="Cost for adaptation ($)"
    )

    # Privacy
    privacy_filter_enabled: bool = Field(
        default=True,
        description="Enable PII filtering before storage"
    )
    sensitive_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{16}\b",  # Credit card
            r"password\s*[:=]\s*\S+",
        ],
        description="Regex patterns for sensitive data"
    )

    class Config:
        """Pydantic settings config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# =============================================================================
# Configuration Loading
# =============================================================================


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = Path(config_path)
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_task_thresholds(task_type: str) -> TaskTypeThresholds:
    """Get thresholds for a specific task type."""
    return THRESHOLDS_CONFIG.get(
        task_type,
        TaskTypeThresholds()  # Default thresholds
    )
