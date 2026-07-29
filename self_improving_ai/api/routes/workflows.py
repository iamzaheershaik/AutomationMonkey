"""Workflow management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from api import get_memory_engine, get_workflow_optimizer
from core.models import WorkflowVersion

router = APIRouter()


@router.post("/")
async def create_workflow(
    name: str,
    steps: dict,
    description: str = "",
    version: str = "1.0.0",
):
    """Register a new workflow version."""
    wf = WorkflowVersion(
        name=name,
        version=version,
        steps=steps,
        description=description,
    )
    saved = get_memory_engine().store_workflow_version(wf)
    return {"workflow_id": saved.id, "name": saved.name, "version": saved.version}


@router.get("/")
async def list_workflows(
    name: Optional[str] = None,
    active_only: bool = False,
    limit: int = Query(default=50, le=200),
):
    """List workflow versions."""
    from core.database import SessionLocal
    from core.models import WorkflowVersion

    with SessionLocal() as db:
        q = db.query(WorkflowVersion)
        if name:
            q = q.filter(WorkflowVersion.name == name)
        if active_only:
            q = q.filter(WorkflowVersion.is_active == True)  # noqa: E712
        workflows = q.order_by(WorkflowVersion.created_at.desc()).limit(limit).all()

    return {
        "count": len(workflows),
        "workflows": [
            {
                "id": w.id,
                "name": w.name,
                "version": w.version,
                "is_active": w.is_active,
                "success_rate": w.success_rate,
                "avg_latency_ms": w.avg_latency_ms,
            }
            for w in workflows
        ],
    }


@router.post("/{workflow_name}/analyze")
async def analyze_workflow(workflow_name: str):
    """Analyze workflow performance."""
    from core.database import SessionLocal
    from core.models import AgentExecution, WorkflowVersion

    with SessionLocal() as db:
        wf = (
            db.query(WorkflowVersion)
            .filter(WorkflowVersion.name == workflow_name, WorkflowVersion.is_active == True)  # noqa: E712
            .first()
        )
        if not wf:
            wf = (
                db.query(WorkflowVersion)
                .filter(WorkflowVersion.name == workflow_name)
                .order_by(WorkflowVersion.created_at.desc())
                .first()
            )
        if not wf:
            return {"error": f"No workflow found with name '{workflow_name}'"}

        executions = (
            db.query(AgentExecution)
            .filter(AgentExecution.agent_name.contains(workflow_name))
            .limit(100)
            .all()
        )

    return get_workflow_optimizer().analyze_workflow(wf, executions)


@router.post("/{workflow_name}/propose-variants")
async def propose_workflow_variants(workflow_name: str):
    """Propose optimized workflow variants."""
    from core.database import SessionLocal
    from core.models import AgentExecution, WorkflowVersion

    with SessionLocal() as db:
        wf = (
            db.query(WorkflowVersion)
            .filter(WorkflowVersion.name == workflow_name, WorkflowVersion.is_active == True)  # noqa: E712
            .first()
        )
        if not wf:
            wf = (
                db.query(WorkflowVersion)
                .filter(WorkflowVersion.name == workflow_name)
                .order_by(WorkflowVersion.created_at.desc())
                .first()
            )
        if not wf:
            return {"error": f"No workflow found with name '{workflow_name}'"}

        executions = (
            db.query(AgentExecution)
            .filter(AgentExecution.agent_name.contains(workflow_name))
            .limit(100)
            .all()
        )

    analysis = get_workflow_optimizer().analyze_workflow(wf, executions)
    variants = get_workflow_optimizer().propose_workflow_variants(wf, analysis)
    return {
        "base_workflow": workflow_name,
        "num_variants": len(variants),
        "variants": [{"id": v.id, "version": v.version, "description": v.description} for v in variants],
    }
