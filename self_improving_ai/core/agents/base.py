"""
Base Agent class providing the foundation for all specialized agents.

Agents are autonomous workers that:
- Receive tasks
- Execute their specialized function
- Report observations
- Can trigger experiments through the Experiment Engine
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog

from core.database import SessionLocal
from core.models import AgentExecution

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """Foundation for all agents in the Self-Improving AI System."""

    agent_name: str = "base_agent"
    agent_version: str = "1.0.0"

    def __init__(self) -> None:
        self.agent_id = uuid.uuid4().hex[:12]
        self._engines: dict[str, Any] = {}
        logger.info("agent.created", name=self.agent_name, id=self.agent_id)

    def set_engines(self, engines: dict[str, Any]) -> None:
        """Inject engine dependencies."""
        self._engines = engines

    @abstractmethod
    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's primary function.

        Args:
            task: Task specification with input data.

        Returns:
            Result dictionary with output and metadata.
        """
        ...

    async def execute_with_trace(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute and record an agent execution in the database."""
        execution = AgentExecution(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            task_id=task.get("task_id", ""),
            status="started",
            input_data=task,
        )

        start_time = time.monotonic()
        steps: list[dict[str, Any]] = []

        try:
            result = await self.execute(task)
            elapsed = (time.monotonic() - start_time) * 1000

            execution.status = "completed"
            execution.output_data = result
            execution.steps = steps
            execution.latency_ms = elapsed
            execution.tokens_used = result.get("tokens_used", 0)
            execution.completed_at = datetime.utcnow()

            logger.info(
                "agent.execution.completed",
                agent=self.agent_name,
                task=task.get("task_id"),
                latency_ms=elapsed,
            )
            return result

        except Exception as exc:
            elapsed = (time.monotonic() - start_time) * 1000
            execution.status = "failed"
            execution.errors = [{"error": str(exc), "type": type(exc).__name__}]
            execution.latency_ms = elapsed
            execution.completed_at = datetime.utcnow()

            logger.error(
                "agent.execution.failed",
                agent=self.agent_name,
                task=task.get("task_id"),
                error=str(exc),
            )
            raise

        finally:
            with SessionLocal() as db:
                db.add(execution)
                db.commit()

    def record_step(
        self,
        steps: list[dict[str, Any]],
        step_name: str,
        success: bool,
        latency_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an individual step during execution."""
        steps.append({
            "name": step_name,
            "success": success,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })
