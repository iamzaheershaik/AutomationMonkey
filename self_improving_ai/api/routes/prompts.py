"""Prompt management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from api import get_memory_engine, get_prompt_optimizer
from core.models import PromptVersion

router = APIRouter()


@router.post("/")
async def create_prompt(
    name: str,
    version: str,
    template: str,
    model: str = "gpt-4",
    variables: Optional[dict] = None,
):
    """Register a new prompt version."""
    prompt = PromptVersion(
        name=name,
        version=version,
        template=template,
        model=model,
        variables=variables or {},
    )
    saved = get_memory_engine().store_prompt_version(prompt)
    return {"prompt_id": saved.id, "name": saved.name, "version": saved.version}


@router.get("/")
async def list_prompts(
    name: Optional[str] = None,
    active_only: bool = False,
    limit: int = Query(default=50, le=200),
):
    """List prompt versions."""
    from core.database import SessionLocal
    from core.models import PromptVersion

    with SessionLocal() as db:
        q = db.query(PromptVersion)
        if name:
            q = q.filter(PromptVersion.name == name)
        if active_only:
            q = q.filter(PromptVersion.is_active == True)  # noqa: E712
        prompts = q.order_by(PromptVersion.created_at.desc()).limit(limit).all()

    return {
        "count": len(prompts),
        "prompts": [
            {
                "id": p.id,
                "name": p.name,
                "version": p.version,
                "model": p.model,
                "is_active": p.is_active,
                "success_rate": p.success_rate,
                "avg_latency_ms": p.avg_latency_ms,
            }
            for p in prompts
        ],
    }


@router.post("/{prompt_name}/analyze")
async def analyze_prompt(
    prompt_name: str,
    failure_cases: list[dict] = None,
    success_cases: list[dict] = None,
):
    """Analyze a prompt's performance."""
    active = get_memory_engine().get_active_prompt(prompt_name)
    if not active:
        from core.database import SessionLocal
        from core.models import PromptVersion

        with SessionLocal() as db:
            active = (
                db.query(PromptVersion)
                .filter(PromptVersion.name == prompt_name)
                .order_by(PromptVersion.created_at.desc())
                .first()
            )
        if not active:
            return {"error": f"No prompt found with name '{prompt_name}'"}

    return get_prompt_optimizer().analyze_prompt(
        active, failure_cases or [], success_cases or []
    )


@router.post("/{prompt_name}/generate-variants")
async def generate_variants(
    prompt_name: str,
    num_variants: int = 5,
    failure_cases: list[dict] = None,
    success_cases: list[dict] = None,
):
    """Generate improved prompt variants."""
    active = get_memory_engine().get_active_prompt(prompt_name)
    if not active:
        from core.database import SessionLocal
        from core.models import PromptVersion

        with SessionLocal() as db:
            active = (
                db.query(PromptVersion)
                .filter(PromptVersion.name == prompt_name)
                .order_by(PromptVersion.created_at.desc())
                .first()
            )
        if not active:
            return {"error": f"No prompt found with name '{prompt_name}'"}

    analysis = get_prompt_optimizer().analyze_prompt(
        active, failure_cases or [], success_cases or []
    )
    variants = get_prompt_optimizer().generate_variants(active, analysis, num_variants)
    return {
        "base_prompt": prompt_name,
        "num_variants": len(variants),
        "variants": [
            {"id": v.id, "version": v.version, "template": v.template[:200] + "..."}
            for v in variants
        ],
    }
