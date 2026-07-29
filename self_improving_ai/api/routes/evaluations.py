"""Evaluation API endpoints."""

from typing import Any

from fastapi import APIRouter, Query

from api import get_evaluation_engine

router = APIRouter()


@router.post("/")
async def evaluate(
    y_true: list[Any],
    y_pred: list[Any],
):
    """Compute evaluation metrics for predictions."""
    result = get_evaluation_engine().evaluate(y_true, y_pred)
    return result.to_dict()


@router.get("/leaderboard")
async def get_leaderboard(limit: int = Query(default=20, le=100)):
    """Get the current leaderboard."""
    entries = get_evaluation_engine().get_leaderboard(limit)
    return {
        "leaderboard": [
            {
                "rank": e.rank,
                "experiment_id": e.experiment_id,
                "composite_score": e.composite_score,
                "accuracy": e.accuracy,
                "f1_score": e.f1_score,
                "success_rate": e.success_rate,
                "latency_ms": e.latency_ms,
                "cost_usd": e.cost_usd,
            }
            for e in entries
        ]
    }


@router.get("/compare")
async def compare_experiments(experiment_a: str, experiment_b: str):
    """Compare two experiments and detect regressions."""
    return get_evaluation_engine().compare_experiments(experiment_a, experiment_b)
