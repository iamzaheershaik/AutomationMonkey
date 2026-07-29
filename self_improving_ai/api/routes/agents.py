"""Agent execution API endpoints."""

from typing import Any

from fastapi import APIRouter, Query

from core.agents import (
    CriticAgent,
    DeploymentAgent,
    HumanApprovalAgent,
    LoggingAgent,
    MonitoringAgent,
    PlanningAgent,
    ReflectionAgent,
    ResearchAgent,
    TestingAgent,
)

router = APIRouter()

# Agent registry
_agents = {
    "planning": PlanningAgent(),
    "reflection": ReflectionAgent(),
    "critic": CriticAgent(),
    "research": ResearchAgent(),
    "testing": TestingAgent(),
    "deployment": DeploymentAgent(),
    "monitoring": MonitoringAgent(),
    "logging": LoggingAgent(),
    "human_approval": HumanApprovalAgent(),
}


def _get_agent(name: str):
    agent = _agents.get(name)
    if not agent:
        return None
    return agent


@router.get("/")
async def list_agents():
    """List all available agents."""
    return {
        "agents": [
            {"name": name, "version": agent.agent_version}
            for name, agent in _agents.items()
        ]
    }


@router.post("/{agent_name}/execute")
async def execute_agent(agent_name: str, task: dict[str, Any]):
    """Execute an agent with a task."""
    agent = _get_agent(agent_name)
    if not agent:
        return {"error": f"Unknown agent: {agent_name}"}

    result = await agent.execute_with_trace(task)
    return {"agent": agent_name, "result": result}


# ------------------------------------------------------------------
# Planning Agent
# ------------------------------------------------------------------

@router.post("/planning/plan")
async def create_plan(goal: str, context: dict[str, Any] = None, constraints: list[str] = None):
    """Generate an execution plan for a goal."""
    agent = _get_agent("planning")
    result = await agent.execute_with_trace({
        "task_id": f"plan_{goal[:20].replace(' ', '_')}",
        "goal": goal,
        "context": context or {},
        "constraints": constraints or [],
    })
    return result


# ------------------------------------------------------------------
# Reflection Agent
# ------------------------------------------------------------------

@router.post("/reflection/reflect")
async def reflect(executions: list[dict], observations: list[dict] = None):
    """Reflect on past executions."""
    agent = _get_agent("reflection")
    result = await agent.execute_with_trace({
        "task_id": "reflection",
        "executions": executions,
        "observations": observations or [],
    })
    return result


# ------------------------------------------------------------------
# Critic Agent
# ------------------------------------------------------------------

@router.post("/critic/critique")
async def critique(content: dict[str, Any], criteria: list[str] = None):
    """Critique content."""
    agent = _get_agent("critic")
    result = await agent.execute_with_trace({
        "task_id": "critique",
        "content": content,
        "criteria": criteria or [],
    })
    return result


# ------------------------------------------------------------------
# Human Approval Agent
# ------------------------------------------------------------------

@router.post("/approval/request")
async def request_approval(
    experiment_id: str,
    experiment_name: str,
    details: dict[str, Any] = None,
    risk_level: str = "minor",
):
    """Request human approval."""
    agent = _get_agent("human_approval")
    result = await agent.execute_with_trace({
        "task_id": f"approval_{experiment_id}",
        "action": "request",
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
        "details": details or {},
        "risk_level": risk_level,
    })
    return result


@router.post("/approval/{approval_id}/approve")
async def approve(approval_id: str, reviewer: str = "admin", comment: str = ""):
    """Approve a pending request."""
    agent = _get_agent("human_approval")
    result = await agent.execute_with_trace({
        "task_id": f"approve_{approval_id}",
        "action": "approve",
        "approval_id": approval_id,
        "reviewer": reviewer,
        "comment": comment,
    })
    return result


@router.post("/approval/{approval_id}/reject")
async def reject(approval_id: str, reviewer: str = "admin", reason: str = ""):
    """Reject a pending request."""
    agent = _get_agent("human_approval")
    result = await agent.execute_with_trace({
        "task_id": f"reject_{approval_id}",
        "action": "reject",
        "approval_id": approval_id,
        "reviewer": reviewer,
        "reason": reason,
    })
    return result


@router.get("/approval/pending")
async def get_pending_approvals():
    """Get all pending approvals."""
    agent = _get_agent("human_approval")
    return {"pending": agent.get_pending()}


# ------------------------------------------------------------------
# Monitoring Agent
# ------------------------------------------------------------------

@router.post("/monitoring/check")
async def run_monitoring_check(metrics: dict[str, Any]):
    """Run a monitoring check cycle."""
    agent = _get_agent("monitoring")
    result = await agent.execute_with_trace({
        "task_id": "monitoring_check",
        "metrics": metrics,
    })
    return result


@router.get("/monitoring/dashboard")
async def monitoring_dashboard():
    """Get monitoring dashboard."""
    agent = _get_agent("monitoring")
    return agent.get_dashboard()


# ------------------------------------------------------------------
# Testing Agent
# ------------------------------------------------------------------

@router.post("/testing/run")
async def run_tests(
    target: dict[str, Any],
    tests: dict[str, Any] = None,
    test_suite: str = "all",
):
    """Run test suites."""
    agent = _get_agent("testing")
    result = await agent.execute_with_trace({
        "task_id": "test_run",
        "target": target,
        "tests": tests or {},
        "test_suite": test_suite,
    })
    return result


# ------------------------------------------------------------------
# Deployment Agent
# ------------------------------------------------------------------

@router.post("/deployment/deploy")
async def deploy(experiment: dict[str, Any], strategy: str = "canary"):
    """Deploy an experiment."""
    agent = _get_agent("deployment")
    result = await agent.execute_with_trace({
        "task_id": f"deploy_{experiment.get('id', 'unknown')}",
        "experiment": experiment,
        "strategy": strategy,
    })
    return result


@router.post("/deployment/rollback")
async def rollback(experiment_id: str, reason: str = "", checkpoint: str = ""):
    """Rollback a deployment."""
    agent = _get_agent("deployment")
    result = await agent.rollback({
        "experiment_id": experiment_id,
        "reason": reason,
        "checkpoint": checkpoint,
    })
    return result
