"""Health check and system status endpoints."""

from fastapi import APIRouter

from api import (
    get_benchmark_engine,
    get_evaluation_engine,
    get_experiment_engine,
    get_memory_engine,
    get_observation_engine,
    get_prompt_optimizer,
    get_tool_optimizer,
    get_workflow_optimizer,
)
from config.settings import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "version": settings.APP_VERSION}


@router.get("/status")
async def system_status():
    """Detailed system status with all engine health checks."""
    engines = {
        "observation": get_observation_engine().health_check(),
        "memory": get_memory_engine().health_check(),
        "evaluation": get_evaluation_engine().health_check(),
        "experiment": get_experiment_engine().health_check(),
        "benchmark": get_benchmark_engine().health_check(),
        "prompt_optimizer": get_prompt_optimizer().health_check(),
        "tool_optimizer": get_tool_optimizer().health_check(),
        "workflow_optimizer": get_workflow_optimizer().health_check(),
    }

    all_healthy = all(engines.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "engines": engines,
    }


@router.get("/metrics")
async def get_metrics():
    """Get metrics from all engines."""
    return {
        "observation": get_observation_engine().get_metrics(),
        "memory": get_memory_engine().get_metrics(),
        "evaluation": get_evaluation_engine().get_metrics(),
        "experiment": get_experiment_engine().get_metrics(),
        "benchmark": get_benchmark_engine().get_metrics(),
    }
