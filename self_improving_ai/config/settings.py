"""
Central configuration for the Self-Improving AI System.
Loads from environment variables with sensible defaults.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment and .env files."""

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------
    APP_NAME: str = "self-improving-ai"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./data/self_improving_ai.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # ------------------------------------------------------------------
    # Redis / Cache
    # ------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = False

    # ------------------------------------------------------------------
    # API Server
    # ------------------------------------------------------------------
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_RELOAD: bool = True

    # ------------------------------------------------------------------
    # LLM Providers
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------
    SHORT_TERM_MEMORY_SIZE: int = 1000
    LONG_TERM_MEMORY_PATH: str = "./data/long_term_memory"
    SEMANTIC_MEMORY_COLLECTION: str = "semantic_memory"
    VECTOR_DB_PATH: str = "./data/vector_db"

    # ------------------------------------------------------------------
    # Experiments
    # ------------------------------------------------------------------
    EXPERIMENT_STORAGE_PATH: str = "./data/experiments"
    MAX_CONCURRENT_EXPERIMENTS: int = 5
    EXPERIMENT_TIMEOUT_SECONDS: int = 3600
    MIN_IMPROVEMENT_THRESHOLD: float = 0.01

    # ------------------------------------------------------------------
    # Safety & Security
    # ------------------------------------------------------------------
    REQUIRE_HUMAN_APPROVAL: bool = True
    AUTO_DEPLOY_ENABLED: bool = False
    MAX_AUTO_CHANGES_PER_DAY: int = 3
    ENCRYPTION_KEY: str = ""
    SECRETS_VAULT_PATH: str = "./data/secrets.enc"

    # ------------------------------------------------------------------
    # Monitoring & Observability
    # ------------------------------------------------------------------
    PROMETHEUS_PORT: int = 9090
    METRICS_ENABLED: bool = True
    TRACING_ENABLED: bool = True
    ALERT_WEBHOOK_URL: str = ""

    # ------------------------------------------------------------------
    # CI/CD
    # ------------------------------------------------------------------
    GIT_REMOTE: str = "origin"
    MAIN_BRANCH: str = "main"
    CANARY_PERCENTAGE: int = 10
    ROLLBACK_ON_FAILURE: bool = True

    # ------------------------------------------------------------------
    # Celery
    # ------------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def ensure_directories() -> None:
    """Create all required data directories on startup."""
    dirs = [
        Path("./data"),
        Path(settings.LONG_TERM_MEMORY_PATH),
        Path(settings.VECTOR_DB_PATH),
        Path(settings.EXPERIMENT_STORAGE_PATH),
        Path("./data/benchmarks"),
        Path("./data/prompts"),
        Path("./data/workflows"),
        Path("./data/tools"),
        Path("./data/logs"),
        Path("./data/rollback"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
