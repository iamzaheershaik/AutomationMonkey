"""Tool management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Query

from api import get_memory_engine, get_tool_optimizer
from core.models import ToolVersion

router = APIRouter()


@router.post("/")
async def register_tool(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    implementation: str = "",
):
    """Register a new tool version."""
    tool = ToolVersion(
        name=name,
        version=version,
        description=description,
        implementation=implementation,
    )
    saved = get_memory_engine().store_tool_version(tool)
    return {"tool_id": saved.id, "name": saved.name, "version": saved.version}


@router.get("/")
async def list_tools(
    name: Optional[str] = None,
    active_only: bool = False,
    limit: int = Query(default=50, le=200),
):
    """List tool versions."""
    from core.database import SessionLocal
    from core.models import ToolVersion

    with SessionLocal() as db:
        q = db.query(ToolVersion)
        if name:
            q = q.filter(ToolVersion.name == name)
        if active_only:
            q = q.filter(ToolVersion.is_active == True)  # noqa: E712
        tools = q.order_by(ToolVersion.created_at.desc()).limit(limit).all()

    return {
        "count": len(tools),
        "tools": [
            {"id": t.id, "name": t.name, "version": t.version, "is_active": t.is_active, "success_rate": t.success_rate}
            for t in tools
        ],
    }


@router.post("/{tool_name}/analyze")
async def analyze_tool(tool_name: str):
    """Analyze tool performance from usage data."""
    from core.database import SessionLocal
    from core.models import ToolUsage, ToolVersion

    with SessionLocal() as db:
        tool = (
            db.query(ToolVersion)
            .filter(ToolVersion.name == tool_name, ToolVersion.is_active == True)  # noqa: E712
            .first()
        )
        if not tool:
            tool = (
                db.query(ToolVersion)
                .filter(ToolVersion.name == tool_name)
                .order_by(ToolVersion.created_at.desc())
                .first()
            )
        if not tool:
            return {"error": f"No tool found with name '{tool_name}'"}

        usages = db.query(ToolUsage).filter(ToolUsage.tool_name == tool_name).limit(1000).all()

    return get_tool_optimizer().analyze_tool(tool, usages)


@router.post("/{tool_name}/suggest-improvements")
async def suggest_tool_improvements(tool_name: str):
    """Suggest tool improvements based on usage analysis."""
    from core.database import SessionLocal
    from core.models import ToolUsage, ToolVersion

    with SessionLocal() as db:
        tool = (
            db.query(ToolVersion)
            .filter(ToolVersion.name == tool_name, ToolVersion.is_active == True)  # noqa: E712
            .first()
        )
        if not tool:
            tool = (
                db.query(ToolVersion)
                .filter(ToolVersion.name == tool_name)
                .order_by(ToolVersion.created_at.desc())
                .first()
            )
        if not tool:
            return {"error": f"No tool found with name '{tool_name}'"}

        usages = db.query(ToolUsage).filter(ToolUsage.tool_name == tool_name).limit(1000).all()

    analysis = get_tool_optimizer().analyze_tool(tool, usages)
    proposals = get_tool_optimizer().propose_improvements(analysis, tool)
    return {"tool_name": tool_name, "current_version": tool.version, "proposals": proposals}
