"""Experiment API endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from api import get_experiment_engine, get_memory_engine
from core.models import ExperimentStatus, ImprovementType

router = APIRouter()


@router.post("/")
async def create_experiment(
    name: str,
    description: str = "",
    improvement_type: ImprovementType = ImprovementType.PROMPT,
    hypothesis: str = "",
    expected_improvement: float = 0.0,
):
    """Propose a new experiment."""
    exp = get_experiment_engine().propose_experiment(
        name=name,
        description=description,
        improvement_type=improvement_type.value,
        hypothesis=hypothesis,
        expected_improvement=expected_improvement,
        proposed_changes={},
    )
    return {"experiment_id": exp.id, "branch": exp.experiment_branch, "status": exp.status}


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get experiment details."""
    from core.database import SessionLocal
    from core.models import Experiment

    with SessionLocal() as db:
        exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        return {"error": "Experiment not found"}
    return {
        "id": exp.id,
        "name": exp.name,
        "status": exp.status,
        "branch": exp.experiment_branch,
        "actual_improvement": exp.actual_improvement,
        "regression_detected": exp.regression_detected,
    }


@router.get("/")
async def list_experiments(
    status: Optional[ExperimentStatus] = None,
    limit: int = Query(default=50, le=200),
):
    """List experiments, optionally filtered by status."""
    from core.database import SessionLocal
    from core.models import Experiment

    with SessionLocal() as db:
        q = db.query(Experiment)
        if status:
            q = q.filter(Experiment.status == status)
        experiments = q.order_by(Experiment.created_at.desc()).limit(limit).all()

    return {
        "count": len(experiments),
        "experiments": [
            {"id": e.id, "name": e.name, "status": e.status, "branch": e.experiment_branch}
            for e in experiments
        ],
    }


@router.post("/{experiment_id}/check-deployable")
async def check_deployable(experiment_id: str):
    """Check if an experiment meets deployment criteria."""
    from core.database import SessionLocal
    from core.models import Experiment

    with SessionLocal() as db:
        exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        return {"error": "Experiment not found"}

    is_deployable, failures = get_experiment_engine().is_deployable(exp)
    return {
        "experiment_id": experiment_id,
        "is_deployable": is_deployable,
        "failures": failures,
    }


@router.post("/{experiment_id}/reject")
async def reject_experiment(experiment_id: str, reason: str = ""):
    """Reject an experiment."""
    from core.database import SessionLocal
    from core.models import Experiment

    with SessionLocal() as db:
        exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        return {"error": "Experiment not found"}

    get_experiment_engine().reject_experiment(exp, reason)
    return {"experiment_id": experiment_id, "status": "rejected"}
