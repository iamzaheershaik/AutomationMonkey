"""Observation API endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from api import get_observation_engine
from core.models import FailureCategory, ObservationType

router = APIRouter()


@router.post("/")
async def record_observation(
    observation_type: ObservationType,
    session_id: str = "",
    task_id: str = "",
    success: Optional[bool] = None,
    error_message: str = "",
    latency_ms: Optional[float] = None,
    cost_usd: Optional[float] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    human_rating: Optional[int] = None,
    human_comment: str = "",
):
    """Record a new observation."""
    obs = get_observation_engine().record_observation(
        observation_type=observation_type,
        session_id=session_id,
        task_id=task_id,
        success=success,
        error_message=error_message,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        human_rating=human_rating,
        human_comment=human_comment,
    )
    return {"observation_id": obs.id, "type": obs.observation_type.value, "timestamp": obs.timestamp.isoformat()}


@router.get("/session/{session_id}")
async def get_session_observations(
    session_id: str,
    limit: int = Query(default=100, le=1000),
):
    """Get observations for a session."""
    obs = get_observation_engine().get_session_observations(session_id, limit)
    return {"session_id": session_id, "count": len(obs), "observations": obs}


@router.get("/failure-rate")
async def get_failure_rate(window_hours: int = Query(default=24)):
    """Get failure rate over a time window."""
    return get_observation_engine().get_failure_rate(window_hours)


@router.get("/failure-categories")
async def get_failure_categories(window_hours: int = Query(default=24)):
    """Get failure breakdown by category."""
    return get_observation_engine().get_category_breakdown(window_hours)
