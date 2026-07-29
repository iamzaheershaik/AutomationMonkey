"""
Reflection Agent

Self-reflects on execution history to identify:
- What went well
- What went wrong
- Lessons learned
- Improvement opportunities

Stores reflections as long-term memory entries.
"""

from __future__ import annotations

from typing import Any

import structlog

from core.agents.base import BaseAgent
from core.models import AgentExecution, Observation

logger = structlog.get_logger(__name__)


class ReflectionAgent(BaseAgent):
    """Analyzes past executions to extract actionable insights."""

    agent_name = "reflection_agent"

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Reflect on recent executions and generate insights."""
        steps: list[dict[str, Any]] = []
        executions = task.get("executions", [])
        observations = task.get("observations", [])

        self.record_step(steps, "analyze_successes", True)
        successes = self._extract_success_patterns(executions)

        self.record_step(steps, "analyze_failures", True)
        failures = self._extract_failure_patterns(executions, observations)

        self.record_step(steps, "extract_lessons", True)
        lessons = self._extract_lessons(successes, failures)

        self.record_step(steps, "generate_improvements", True)
        improvements = self._generate_improvement_ideas(lessons, failures)

        reflection = {
            "num_executions_analyzed": len(executions),
            "success_patterns": successes,
            "failure_patterns": failures,
            "lessons_learned": lessons,
            "improvement_ideas": improvements,
            "summary": self._summarize(lessons, failures, successes),
        }

        logger.info(
            "reflection.completed",
            successes=len(successes),
            failures=len(failures),
            improvements=len(improvements),
        )
        return {"reflection": reflection, "steps": steps, "tokens_used": 0}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_success_patterns(
        self, executions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Identify common patterns in successful executions."""
        successful = [e for e in executions if e.get("status") == "completed"]
        if not successful:
            return []

        patterns = []
        avg_latency = sum(e.get("latency_ms", 0) for e in successful) / len(successful)

        patterns.append({
            "pattern": "successful_completion",
            "frequency": len(successful),
            "avg_latency_ms": avg_latency,
            "insight": "Consistently successful execution pattern identified",
        })

        return patterns

    def _extract_failure_patterns(
        self,
        executions: list[dict[str, Any]],
        observations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify common failure patterns."""
        failed = [e for e in executions if e.get("status") == "failed"]
        if not failed:
            return []

        patterns = []
        error_types: dict[str, int] = {}
        for f in failed:
            errors = f.get("errors", [])
            for err in errors:
                etype = err.get("type", "Unknown")
                error_types[etype] = error_types.get(etype, 0) + 1

        for etype, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            patterns.append({
                "error_type": etype,
                "count": count,
                "frequency": count / max(len(failed), 1),
                "recommended_action": self._recommend_for_error(etype),
            })

        return patterns

    def _extract_lessons(
        self,
        successes: list[dict[str, Any]],
        failures: list[dict[str, Any]],
    ) -> list[str]:
        """Extract actionable lessons from both successes and failures."""
        lessons = []

        if successes:
            lessons.append("Maintain successful execution patterns as baselines")

        for failure in failures:
            error_type = failure.get("error_type", "")
            if "Timeout" in error_type:
                lessons.append("Add timeout handling and circuit breakers")
            elif "ValueError" in error_type or "ValidationError" in error_type:
                lessons.append("Add input validation before execution")
            elif "ConnectionError" in error_type:
                lessons.append("Add retry logic with exponential backoff")

        if not lessons:
            lessons.append("Continue monitoring for patterns")

        return lessons

    def _generate_improvement_ideas(
        self,
        lessons: list[str],
        failures: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate concrete improvement ideas from lessons."""
        ideas = []
        for i, lesson in enumerate(lessons):
            ideas.append({
                "id": i + 1,
                "lesson": lesson,
                "priority": "high" if len(failures) > 5 else "medium",
                "effort": "medium",
                "impact": "high",
            })
        return ideas

    def _summarize(
        self,
        lessons: list[str],
        failures: list[dict[str, Any]],
        successes: list[dict[str, Any]],
    ) -> str:
        """Generate a human-readable summary of the reflection."""
        parts = []
        parts.append(f"Analyzed {len(successes)} successes and {len(failures)} failures.")
        if lessons:
            parts.append(f"Key lessons: {'; '.join(lessons[:3])}.")
        return " ".join(parts)

    @staticmethod
    def _recommend_for_error(error_type: str) -> str:
        recommendations = {
            "TimeoutError": "Increase timeout or add circuit breaker",
            "ValueError": "Add input validation layer",
            "ConnectionError": "Add retry mechanism with backoff",
            "PermissionError": "Review and adjust permission settings",
            "RateLimitError": "Add rate limiting and queuing",
        }
        return recommendations.get(error_type, "Investigate error pattern")
