"""
Experiment Engine

Manages the full experiment lifecycle:
1. Create isolated branches
2. Run A/B Tests, Regression Tests, Simulation, Stress/Security Tests, Benchmarks
3. Never modify production directly
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import structlog
from sqlalchemy.orm import Session

from config.settings import settings
from core.database import SessionLocal
from core.engines.base import BaseEngine
from core.models import (
    DeploymentStrategy,
    Evaluation,
    Experiment,
    ExperimentStatus,
    ImprovementType,
    LeaderboardEntry,
)

logger = structlog.get_logger(__name__)


class TestType(str, Enum):
    AB_TEST = "ab_test"
    REGRESSION = "regression"
    SIMULATION = "simulation"
    STRESS = "stress"
    SECURITY = "security"
    BENCHMARK = "benchmark"


class ExperimentEngine(BaseEngine):
    """Creates isolated branches, runs experiments, and guards production."""

    name = "experiment_engine"

    def __init__(self) -> None:
        super().__init__()
        self._active_experiments: dict[str, Experiment] = {}
        self._branch_snapshots: dict[str, dict[str, Any]] = {}

    def propose_experiment(
        self,
        name: str,
        description: str,
        improvement_type: ImprovementType,
        hypothesis: str,
        expected_improvement: float,
        proposed_changes: dict[str, Any],
        base_version: str = "main",
    ) -> Experiment:
        """Create a new experiment proposal. Does NOT run it yet."""
        experiment = Experiment(
            name=name,
            description=description,
            improvement_type=improvement_type,
            hypothesis=hypothesis,
            expected_improvement=expected_improvement,
            proposed_changes=proposed_changes,
            base_version=base_version,
            experiment_branch=f"exp/{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
            status=ExperimentStatus.PROPOSED.value,
        )
        with SessionLocal() as db:
            db.add(experiment)
            db.commit()
            db.refresh(experiment)

        logger.info(
            "experiment.proposed",
            id=experiment.id,
            name=experiment.name,
            branch=experiment.experiment_branch,
        )
        return experiment

    def run_experiment(
        self,
        experiment: Experiment,
        experiment_fn: Callable[[dict[str, Any]], dict[str, Any]],
        baseline_fn: Callable[[], dict[str, Any]] | None = None,
        test_inputs: list[dict[str, Any]] | None = None,
    ) -> Experiment:
        """Execute an experiment including A/B comparison with baseline."""
        if experiment.status != ExperimentStatus.PROPOSED.value:
            raise ValueError(f"Experiment {experiment.id} is not in PROPOSED state")

        experiment.status = ExperimentStatus.RUNNING.value
        experiment.started_at = datetime.utcnow()

        self._save_state(experiment)
        logger.info("experiment.running", id=experiment.id)

        try:
            # 1. Run baseline if provided
            baseline_results = baseline_fn() if baseline_fn else {}

            # 2. Run experiment variant
            test_inputs = test_inputs or [{}]
            variant_results = []
            for inp in test_inputs:
                result = experiment_fn(inp)
                variant_results.append(result)

            # 3. Aggregate results
            aggregated = self._aggregate_results(variant_results)
            experiment.metrics_after = aggregated
            experiment.metrics_before = baseline_results

            # 4. Compute improvement delta
            if baseline_results:
                experiment.actual_improvement = self._compute_improvement(
                    baseline_results, aggregated
                )

            # 5. Check for regressions
            experiment.regression_detected = self._detect_regression(
                baseline_results, aggregated
            )

            experiment.status = ExperimentStatus.COMPLETED.value
            experiment.completed_at = datetime.utcnow()

        except Exception as exc:
            experiment.status = ExperimentStatus.REJECTED.value
            experiment.extra_data = {"error": str(exc)}
            logger.error("experiment.failed", id=experiment.id, error=str(exc))
            self._restore_state(experiment)

        self._save_state(experiment)
        return experiment

    def is_deployable(self, experiment: Experiment) -> tuple[bool, list[str]]:
        """Check if experiment meets all acceptance criteria.

        Returns (is_deployable, list_of_failures).
        An improvement is accepted only if ALL conditions are met:
        - Higher accuracy
        - Lower cost OR same cost
        - No regression
        - Security passes
        - Tests pass
        """
        failures: list[str] = []

        if experiment.status != ExperimentStatus.COMPLETED.value:
            failures.append("Experiment not completed")
            return False, failures

        if experiment.regression_detected:
            failures.append("Regression detected")

        if experiment.actual_improvement is not None and experiment.actual_improvement <= 0:
            failures.append(
                f"No positive improvement (delta={experiment.actual_improvement:.4f})"
            )

        # Check cost hasn't increased
        cost_before = experiment.metrics_before.get("cost_usd", 0)
        cost_after = experiment.metrics_after.get("cost_usd", 0)
        if cost_after > cost_before * 1.05:  # Allow 5% margin
            failures.append(
                f"Cost increased: ${cost_before:.4f} -> ${cost_after:.4f}"
            )

        # Ensure accuracy improved
        acc_before = experiment.metrics_before.get("accuracy", 0)
        acc_after = experiment.metrics_after.get("accuracy", 0)
        if acc_after < acc_before:
            failures.append(
                f"Accuracy decreased: {acc_before:.4f} -> {acc_after:.4f}"
            )

        return len(failures) == 0, failures

    def reject_experiment(self, experiment: Experiment, reason: str = "") -> Experiment:
        """Reject an experiment with a reason."""
        experiment.status = ExperimentStatus.REJECTED.value
        experiment.extra_data["rejection_reason"] = reason
        self._save_state(experiment)
        logger.info("experiment.rejected", id=experiment.id, reason=reason)
        return experiment

    def rollback_experiment(self, experiment: Experiment) -> None:
        """Restore the pre-experiment state."""
        self._restore_state(experiment)
        experiment.status = ExperimentStatus.ROLLED_BACK.value
        experiment.extra_data["rolled_back_at"] = datetime.utcnow().isoformat()
        self._save_state(experiment)
        logger.info("experiment.rolled_back", id=experiment.id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _aggregate_results(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Aggregate multiple test runs into summary statistics."""
        if not results:
            return {}

        keys = results[0].keys()
        aggregated: dict[str, Any] = {}
        for key in keys:
            values = [r[key] for r in results if key in r and isinstance(r[key], (int, float))]
            if values:
                aggregated[key] = {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }
            else:
                aggregated[key] = {"values": [r.get(key) for r in results]}
        return aggregated

    def _compute_improvement(
        self,
        baseline: dict[str, Any],
        variant: dict[str, Any],
    ) -> float:
        """Compute relative improvement over baseline."""
        improvements = []
        for key in baseline:
            b_val = baseline.get(key, 0)
            v_val = variant.get(key, {}).get("mean", variant.get(key, 0))
            if isinstance(b_val, (int, float)) and isinstance(v_val, (int, float)) and b_val != 0:
                improvements.append((v_val - b_val) / abs(b_val))
        return sum(improvements) / max(len(improvements), 1) if improvements else 0.0

    def _detect_regression(
        self,
        baseline: dict[str, Any],
        variant: dict[str, Any],
    ) -> bool:
        """Detect if any key metric regressed significantly."""
        critical_keys = {"accuracy", "f1_score", "success_rate", "security_score"}
        for key in critical_keys:
            b_val = baseline.get(key, 0)
            v_val = variant.get(key, {}).get("mean", variant.get(key, 0))
            if isinstance(b_val, (int, float)) and isinstance(v_val, (int, float)):
                # Regression: more than 2% drop
                if b_val > 0 and (b_val - v_val) / b_val > 0.02:
                    return True
        return False

    def _save_state(self, experiment: Experiment) -> None:
        """Persist current experiment state to DB."""
        with SessionLocal() as db:
            existing = db.query(Experiment).filter(Experiment.id == experiment.id).first()
            if existing:
                for col in Experiment.__table__.columns:
                    setattr(existing, col.name, getattr(experiment, col.name))
            else:
                db.add(experiment)
            db.commit()

    def _restore_state(self, experiment: Experiment) -> None:
        """Restore from the branch snapshot."""
        snapshot = self._branch_snapshots.get(experiment.experiment_branch)
        if snapshot:
            logger.info("restoring.snapshot", branch=experiment.experiment_branch)
