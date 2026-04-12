"""Configuration management for SFE."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# Task Type Thresholds


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


# Main Settings


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
    # IVF-PQ/OPQ optimization settings
    vector_use_ivf_pq: bool = Field(
        default=False,
        description="Enable IVF-PQ indexing for better scalability with large vector datasets"
    )
    vector_use_opq: bool = Field(
        default=False,
        description="Enable OPQ (Optimized Product Quantization) for better quantization accuracy"
    )
    vector_ivf_nlist: int = Field(
        default=100,
        description="Number of Voronoi cells for IVF indexing"
    )
    vector_nprobe: int = Field(
        default=10,
        description="Number of cells to visit during IVF search (higher = more accurate but slower)"
    )
    vector_pq_m: int = Field(
        default=16,
        description="Number of subquantizers for PQ"
    )
    vector_pq_nbits: int = Field(
        default=8,
        description="Bits per subquantizer for PQ"
    )
    vector_opq_train_iterations: int = Field(
        default=20,
        description="Number of training iterations for OPQ"
    )

    # Clustering
    clustering_enabled: bool = Field(
        default=False,
        description="Enable automatic clustering of fragments"
    )
    clustering_method: str = Field(
        default="auto",
        description="Clustering method (auto, kmeans, dbscan, hierarchical)"
    )
    clustering_min_clusters: int = Field(
        default=2,
        description="Minimum number of clusters"
    )
    clustering_max_clusters: int = Field(
        default=50,
        description="Maximum number of clusters"
    )

    # Encryption
    encryption_enabled: bool = Field(
        default=False,
        description="Enable encryption for sensitive fragment data"
    )
    encryption_key: str | None = Field(
        default=None,
        description="Fernet encryption key (base64 encoded)"
    )
    encryption_password: str = Field(
        default="default_password",
        description="Password to derive encryption key if key not provided"
    )
    encryption_salt: bytes = Field(
        default=b'skill_fragment_engine_salt',
        description="Salt for key derivation"
    )
    encryption_sensitive_fields: list[str] = Field(
        default_factory=lambda: ["prompt", "result", "context"],
        description="Fields to encrypt in fragments"
    )

    # RBAC
    rbac_enabled: bool = Field(
        default=False,
        description="Enable RBAC for API access control"
    )
    rbac_default_role: str = Field(
        default="user",
        description="Default role for unauthenticated users"
    )

    # Audit Logging
    audit_enabled: bool = Field(
        default=True,
        description="Enable audit logging"
    )
    audit_log_path: str = Field(
        default="./data/audit.json",
        description="Path to audit log file"
    )
    audit_max_events: int = Field(
        default=10000,
        description="Maximum events to keep in audit log"
    )

    # Anonymization
    anonymization_enabled: bool = Field(
        default=False,
        description="Enable anonymization of PII in fragments"
    )
    anonymization_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\b[A-Z]{2}\d{6,9}\b",  # ID numbers
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{16}\b",  # Credit card
            r"\b[\w.-]+@[\w.-]+\.\w+\b",  # Email
        ],
        description="Regex patterns for PII detection"
    )
    anonymization_replacement: str = Field(
        default="[REDACTED]",
        description="Replacement text for PII"
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
    similarity_algorithm: str = Field(
        default="jaccard",
        description="Similarity algorithm to use for keyword matching (jaccard, cosine, dice)"
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


# Configuration Loading


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
