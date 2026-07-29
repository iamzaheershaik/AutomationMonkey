"""
FastAPI application factory and lifecycle management.

Provides:
- Centralized FastAPI app creation
- Engine initialization
- Agent initialization
- Lifecycle hooks
- Dependency injection
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import ensure_directories, settings
from core.database import init_db
from core.engines import (
    BenchmarkEngine,
    EvaluationEngine,
    ExperimentEngine,
    MemoryEngine,
    ObservationEngine,
    PromptOptimizer,
    ToolOptimizer,
    WorkflowOptimizer,
)

logger = structlog.get_logger(__name__)

# Global engine instances (lifetime = application lifetime)
_observation_engine: ObservationEngine | None = None
_memory_engine: MemoryEngine | None = None
_evaluation_engine: EvaluationEngine | None = None
_experiment_engine: ExperimentEngine | None = None
_benchmark_engine: BenchmarkEngine | None = None
_prompt_optimizer: PromptOptimizer | None = None
_tool_optimizer: ToolOptimizer | None = None
_workflow_optimizer: WorkflowOptimizer | None = None


def get_observation_engine() -> ObservationEngine:
    assert _observation_engine is not None, "ObservationEngine not initialized"
    return _observation_engine


def get_memory_engine() -> MemoryEngine:
    assert _memory_engine is not None, "MemoryEngine not initialized"
    return _memory_engine


def get_evaluation_engine() -> EvaluationEngine:
    assert _evaluation_engine is not None, "EvaluationEngine not initialized"
    return _evaluation_engine


def get_experiment_engine() -> ExperimentEngine:
    assert _experiment_engine is not None, "ExperimentEngine not initialized"
    return _experiment_engine


def get_benchmark_engine() -> BenchmarkEngine:
    assert _benchmark_engine is not None, "BenchmarkEngine not initialized"
    return _benchmark_engine


def get_prompt_optimizer() -> PromptOptimizer:
    assert _prompt_optimizer is not None, "PromptOptimizer not initialized"
    return _prompt_optimizer


def get_tool_optimizer() -> ToolOptimizer:
    assert _tool_optimizer is not None, "ToolOptimizer not initialized"
    return _tool_optimizer


def get_workflow_optimizer() -> WorkflowOptimizer:
    assert _workflow_optimizer is not None, "WorkflowOptimizer not initialized"
    return _workflow_optimizer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    global _observation_engine, _memory_engine, _evaluation_engine
    global _experiment_engine, _benchmark_engine
    global _prompt_optimizer, _tool_optimizer, _workflow_optimizer

    # Startup
    logger.info("application.starting", environment=settings.ENVIRONMENT)
    ensure_directories()
    init_db()

    _observation_engine = ObservationEngine()
    _memory_engine = MemoryEngine()
    _evaluation_engine = EvaluationEngine()
    _experiment_engine = ExperimentEngine()
    _benchmark_engine = BenchmarkEngine()
    _prompt_optimizer = PromptOptimizer()
    _tool_optimizer = ToolOptimizer()
    _workflow_optimizer = WorkflowOptimizer()

    engines = [
        _observation_engine,
        _memory_engine,
        _evaluation_engine,
        _experiment_engine,
        _benchmark_engine,
        _prompt_optimizer,
        _tool_optimizer,
        _workflow_optimizer,
    ]

    for engine in engines:
        engine.start()

    logger.info("application.started", engines=len(engines))
    yield

    # Shutdown
    logger.info("application.stopping")
    for engine in engines:
        engine.stop()
    logger.info("application.stopped")


def create_app() -> FastAPI:
    """Factory: create and configure the FastAPI application."""
    app = FastAPI(
        title="Self-Improving AI System",
        description="A production-grade AI platform that continuously optimizes itself.",
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from api.routes import observations, experiments, evaluations, prompts, tools, workflows, agents, health

    app.include_router(health.router, tags=["Health"])
    app.include_router(observations.router, prefix="/api/v1/observations", tags=["Observations"])
    app.include_router(experiments.router, prefix="/api/v1/experiments", tags=["Experiments"])
    app.include_router(evaluations.router, prefix="/api/v1/evaluations", tags=["Evaluations"])
    app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["Prompts"])
    app.include_router(tools.router, prefix="/api/v1/tools", tags=["Tools"])
    app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])

    return app


app = create_app()
