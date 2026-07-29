"""
Workflow Optimizer Engine

Analyzes multi-step workflows and proposes improvements:
- Step reordering for efficiency
- Parallelization opportunities
- Step removal / consolidation
- Better tool selection
- Conditional branching optimization
"""

from __future__ import annotations

from typing import Any

import structlog

from core.engines.base import BaseEngine
from core.models import AgentExecution, WorkflowVersion

logger = structlog.get_logger(__name__)


class WorkflowOptimizer(BaseEngine):
    """Optimizes multi-step agent workflows based on execution data."""

    name = "workflow_optimizer"

    def analyze_workflow(
        self,
        workflow: WorkflowVersion,
        executions: list[AgentExecution],
    ) -> dict[str, Any]:
        """Analyze workflow performance from execution history."""
        total = len(executions)
        successes = [e for e in executions if e.status == "completed"]
        failures = [e for e in executions if e.status == "failed"]

        success_rate = len(successes) / max(total, 1)
        avg_latency = sum(e.latency_ms or 0 for e in executions) / max(total, 1)
        avg_cost = sum(e.cost_usd or 0 for e in executions) / max(total, 1)

        # Analyze per-step performance
        step_metrics: dict[str, dict[str, Any]] = {}
        for e in executions:
            for step in e.steps or []:
                step_name = step.get("name", "unknown")
                if step_name not in step_metrics:
                    step_metrics[step_name] = {
                        "count": 0,
                        "failures": 0,
                        "total_latency_ms": 0,
                        "avg_latency_ms": 0,
                    }
                sm = step_metrics[step_name]
                sm["count"] += 1
                sm["total_latency_ms"] += step.get("latency_ms", 0)
                if not step.get("success", True):
                    sm["failures"] += 1

        for name, metrics in step_metrics.items():
            metrics["avg_latency_ms"] = (
                metrics["total_latency_ms"] / max(metrics["count"], 1)
            )
            metrics["failure_rate"] = (
                metrics["failures"] / max(metrics["count"], 1)
            )

        # Identify bottlenecks (slowest steps)
        bottlenecks = sorted(
            step_metrics.items(),
            key=lambda x: x[1]["avg_latency_ms"],
            reverse=True,
        )[:3]

        # Identify parallelization opportunities
        parallel_candidates = self._find_parallelization(workflow, step_metrics)

        analysis = {
            "workflow_name": workflow.name,
            "workflow_version": workflow.version,
            "total_executions": total,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "avg_cost_usd": avg_cost,
            "step_metrics": {k: v for k, v in step_metrics.items()},
            "bottlenecks": [
                {"step": name, "avg_latency_ms": m["avg_latency_ms"]}
                for name, m in bottlenecks
            ],
            "parallelization_opportunities": parallel_candidates,
            "recommendations": [],
        }

        # Generate recommendations
        if success_rate < 0.90:
            analysis["recommendations"].append({
                "priority": "high",
                "type": "reliability",
                "action": "Add retry logic and error recovery steps",
            })

        for name, m in bottlenecks:
            if m["avg_latency_ms"] > 2000:
                analysis["recommendations"].append({
                    "priority": "high",
                    "type": "performance",
                    "action": f"Optimize bottleneck step '{name}' ({m['avg_latency_ms']:.0f}ms avg)",
                })

        if parallel_candidates:
            analysis["recommendations"].append({
                "priority": "medium",
                "type": "parallelization",
                "action": f"Parallelize {len(parallel_candidates)} independent step groups",
            })

        return analysis

    def propose_workflow_variants(
        self,
        base_workflow: WorkflowVersion,
        analysis: dict[str, Any],
    ) -> list[WorkflowVersion]:
        """Generate workflow variant proposals."""
        variants: list[WorkflowVersion] = []

        # Variant 1: Parallelized version
        parallel_steps = analysis.get("parallelization_opportunities", [])
        if parallel_steps:
            new_steps = self._apply_parallelization(
                base_workflow.steps, parallel_steps
            )
            variants.append(
                WorkflowVersion(
                    name=base_workflow.name,
                    version=f"{base_workflow.version}.parallel",
                    steps=new_steps,
                    description=base_workflow.description + " (parallelized)",
                    is_active=False,
                )
            )

        # Variant 2: Optimized ordering
        reordered_steps = self._reorder_by_dependency(
            base_workflow.steps, analysis.get("step_metrics", {})
        )
        variants.append(
            WorkflowVersion(
                name=base_workflow.name,
                version=f"{base_workflow.version}.reordered",
                steps=reordered_steps,
                description=base_workflow.description + " (reordered)",
                is_active=False,
            )
        )

        # Variant 3: With retry logic
        retry_steps = self._add_retry_logic(base_workflow.steps)
        variants.append(
            WorkflowVersion(
                name=base_workflow.name,
                version=f"{base_workflow.version}.retry",
                steps=retry_steps,
                description=base_workflow.description + " (with retries)",
                is_active=False,
            )
        )

        return variants

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_parallelization(
        workflow: WorkflowVersion,
        step_metrics: dict[str, dict[str, Any]],
    ) -> list[list[str]]:
        """Find groups of steps that can run in parallel."""
        steps = workflow.steps.get("sequence", [])
        deps = workflow.steps.get("dependencies", {})

        # Identify steps with no inter-dependencies
        independent_groups: list[list[str]] = []
        visited: set[str] = set()

        for i, step_a in enumerate(steps):
            step_name_a = step_a if isinstance(step_a, str) else step_a.get("name", "")
            if step_name_a in visited:
                continue

            group = [step_name_a]
            visited.add(step_name_a)

            for j, step_b in enumerate(steps):
                if j <= i:
                    continue
                step_name_b = step_b if isinstance(step_b, str) else step_b.get("name", "")

                # Check if neither depends on the other
                dep_a = deps.get(step_name_a, [])
                dep_b = deps.get(step_name_b, [])
                if step_name_a not in dep_b and step_name_b not in dep_a:
                    group.append(step_name_b)
                    visited.add(step_name_b)

            if len(group) > 1:
                independent_groups.append(group)

        return independent_groups

    @staticmethod
    def _apply_parallelization(
        steps: dict[str, Any],
        parallel_groups: list[list[str]],
    ) -> dict[str, Any]:
        """Transform sequential steps into parallel groups."""
        new_steps = copy.deepcopy(steps)
        new_steps["parallel_groups"] = parallel_groups
        new_steps["execution_mode"] = "parallel_where_possible"
        return new_steps

    @staticmethod
    def _reorder_by_dependency(
        steps: dict[str, Any],
        step_metrics: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Reorder steps to put fast steps first (within dependency constraints)."""
        return copy.deepcopy(steps)  # Placeholder: full topological sort by latency

    @staticmethod
    def _add_retry_logic(steps: dict[str, Any]) -> dict[str, Any]:
        """Add retry configuration to each step."""
        new_steps = copy.deepcopy(steps)
        new_steps["default_retry_policy"] = {
            "max_retries": 3,
            "backoff_factor": 2.0,
            "retry_on": ["timeout", "connection_error", "rate_limit"],
        }
        return new_steps


import copy  # noqa: E402
