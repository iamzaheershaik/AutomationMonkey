"""
Tool Optimizer Engine

Analyzes tool usage patterns and proposes improvements:
- Faster implementations
- Better error handling
- Improved signatures
- New tool creation
- Tool deprecation
"""

from __future__ import annotations

from typing import Any

import structlog

from core.engines.base import BaseEngine
from core.models import ToolUsage, ToolVersion

logger = structlog.get_logger(__name__)


class ToolOptimizer(BaseEngine):
    """Analyzes tool performance and proposes optimized versions."""

    name = "tool_optimizer"

    def analyze_tool(
        self,
        tool: ToolVersion,
        usages: list[ToolUsage],
    ) -> dict[str, Any]:
        """Analyze tool performance from usage data.

        Returns recommendations for improvement.
        """
        total = len(usages)
        failures = [u for u in usages if not u.success]
        failure_rate = len(failures) / max(total, 1)
        avg_latency = sum(u.latency_ms or 0 for u in usages) / max(total, 1)
        avg_cost = sum(u.cost_usd or 0 for u in usages) / max(total, 1)

        analysis = {
            "tool_name": tool.name,
            "tool_version": tool.version,
            "total_usages": total,
            "failure_rate": failure_rate,
            "avg_latency_ms": avg_latency,
            "avg_cost_usd": avg_cost,
            "recommendations": [],
        }

        # Failure pattern analysis
        if failure_rate > 0.05:
            failure_args: dict[str, int] = {}
            for f in failures:
                args_str = str(sorted(f.arguments.keys()))
                failure_args[args_str] = failure_args.get(args_str, 0) + 1

            analysis["recommendations"].append({
                "priority": "high",
                "type": "error_handling",
                "reason": f"High failure rate ({failure_rate:.1%})",
                "action": "Add input validation and better error handling",
                "failure_patterns": dict(
                    sorted(failure_args.items(), key=lambda x: x[1], reverse=True)[:5]
                ),
            })

        # Latency recommendations
        if avg_latency > 1000:
            analysis["recommendations"].append({
                "priority": "medium",
                "type": "performance",
                "reason": f"High latency ({avg_latency:.0f}ms avg)",
                "action": "Consider caching, batching, or async execution",
            })

        # Cost recommendations
        if avg_cost > 0.01:
            analysis["recommendations"].append({
                "priority": "medium",
                "type": "cost_optimization",
                "reason": f"High average cost (${avg_cost:.4f})",
                "action": "Cache frequent results; reduce token usage",
            })

        return analysis

    def propose_improvements(
        self,
        analysis: dict[str, Any],
        base_tool: ToolVersion,
    ) -> list[dict[str, Any]]:
        """Generate concrete improvement proposals for a tool."""
        proposals: list[dict[str, Any]] = []

        for rec in analysis.get("recommendations", []):
            proposal = {
                "base_tool": base_tool.name,
                "current_version": base_tool.version,
                "recommendation": rec,
                "proposed_changes": {},
            }

            if rec["type"] == "error_handling":
                proposal["proposed_changes"] = {
                    "add_input_validation": True,
                    "add_retry_logic": True,
                    "add_error_codes": True,
                }
            elif rec["type"] == "performance":
                proposal["proposed_changes"] = {
                    "add_caching": True,
                    "batch_processing": True,
                    "async_execution": True,
                }

            proposals.append(proposal)

        return proposals

    def suggest_new_tools(
        self,
        failure_categories: dict[str, int],
        existing_tools: list[str],
    ) -> list[dict[str, Any]]:
        """Suggest new tools based on failure patterns and gaps."""
        suggestions = []

        failure_to_tool_map = {
            "hallucination": {
                "name": "fact_checker",
                "description": "Cross-reference claims against trusted sources",
                "signature": {"claim": "str", "sources": "list[str]"},
            },
            "parse_error": {
                "name": "output_validator",
                "description": "Validate output format against expected schema",
                "signature": {"output": "str", "schema": "dict"},
            },
            "timeout": {
                "name": "circuit_breaker",
                "description": "Detect and handle timeout conditions gracefully",
                "signature": {"operation": "str", "timeout_ms": "int"},
            },
        }

        for category, count in failure_categories.items():
            if category in failure_to_tool_map:
                tool_spec = failure_to_tool_map[category]
                if tool_spec["name"] not in existing_tools:
                    suggestions.append({
                        "name": tool_spec["name"],
                        "description": tool_spec["description"],
                        "signature": tool_spec["signature"],
                        "triggered_by": f"{count} failures in category '{category}'",
                        "priority": "high" if count > 5 else "medium",
                    })

        return suggestions

    def create_tool_version(
        self,
        base: ToolVersion,
        improvements: dict[str, Any],
        version_bump: str = "patch",
    ) -> ToolVersion:
        """Create a new version of a tool with applied improvements."""
        parts = [int(x) for x in base.version.split(".")]
        if version_bump == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        elif version_bump == "minor":
            parts[1] += 1
            parts[2] = 0
        else:
            parts[2] += 1

        new_version = ".".join(str(p) for p in parts)

        return ToolVersion(
            name=base.name,
            version=new_version,
            description=base.description,
            implementation=base.implementation,
            signature={**base.signature, "improvements": improvements},
            is_active=False,
        )
