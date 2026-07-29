"""
Evaluation Engine

Measures:
- Accuracy
- Precision
- Recall
- F1 Score
- Latency
- Cost
- Success Rate
- User Satisfaction
- Reliability
- Security Score

Maintains a leaderboard of experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import structlog
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.engines.base import BaseEngine
from core.models import Evaluation, Experiment, LeaderboardEntry

logger = structlog.get_logger(__name__)


@dataclass
class EvaluationResult:
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    success_rate: float = 0.0
    user_satisfaction: float = 0.0
    reliability: float = 0.0
    security_score: float = 0.0
    composite_score: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "success_rate": self.success_rate,
            "user_satisfaction": self.user_satisfaction,
            "reliability": self.reliability,
            "security_score": self.security_score,
            "composite_score": self.composite_score,
        }


class EvaluationEngine(BaseEngine):
    """Measures and tracks experiment performance on all metrics."""

    name = "evaluation_engine"

    def evaluate(
        self,
        y_true: list[Any],
        y_pred: list[Any],
        metrics_before: dict[str, float] | None = None,
    ) -> EvaluationResult:
        """Compute all evaluation metrics from prediction results.

        For classification tasks, expects y_true and y_pred as label lists.
        For other task types, adapt accordingly.
        """
        result = EvaluationResult()

        yt = np.array(y_true)
        yp = np.array(y_pred)

        correct = (yt == yp).sum()
        total = len(yt)
        result.accuracy = correct / max(total, 1)

        # Per-class P/R/F1 (macro average)
        classes = np.unique(np.concatenate([yt, yp]))
        precisions = []
        recalls = []
        for cls in classes:
            tp = ((yp == cls) & (yt == cls)).sum()
            fp = ((yp == cls) & (yt != cls)).sum()
            fn = ((yp != cls) & (yt == cls)).sum()
            precisions.append(tp / max(tp + fp, 1))
            recalls.append(tp / max(tp + fn, 1))

        result.precision = np.mean(precisions) if precisions else 0.0
        result.recall = np.mean(recalls) if recalls else 0.0
        result.f1_score = (
            2 * result.precision * result.recall / max(result.precision + result.recall, 1e-9)
        )

        result.composite_score = self._compute_composite(result)
        return result

    def compare_experiments(
        self,
        experiment_a: str,
        experiment_b: str,
    ) -> dict[str, Any]:
        """Compare two experiments and detect regressions."""
        with SessionLocal() as db:
            evals_a = (
                db.query(Evaluation)
                .filter(Evaluation.experiment_id == experiment_a)
                .all()
            )
            evals_b = (
                db.query(Evaluation)
                .filter(Evaluation.experiment_id == experiment_b)
                .all()
            )

        comparisons = []
        regressions = []

        for ea in evals_a:
            match = next((eb for eb in evals_b if eb.metric_name == ea.metric_name), None)
            if match:
                delta = (match.value_after or 0) - (ea.value_after or 0)
                is_regression = delta < 0 and "latency" not in ea.metric_name and "cost" not in ea.metric_name
                comparisons.append({
                    "metric": ea.metric_name,
                    "before": ea.value_after,
                    "after": match.value_after,
                    "delta": delta,
                    "regression": is_regression,
                })
                if is_regression:
                    regressions.append(ea.metric_name)

        return {
            "comparisons": comparisons,
            "regressions_detected": regressions,
            "has_regression": len(regressions) > 0,
        }

    def update_leaderboard(self, experiment_id: str, result: EvaluationResult) -> LeaderboardEntry:
        """Update the leaderboard with evaluation results."""
        with SessionLocal() as db:
            existing = (
                db.query(LeaderboardEntry)
                .filter(LeaderboardEntry.experiment_id == experiment_id)
                .first()
            )

            if existing:
                existing.accuracy = result.accuracy
                existing.precision = result.precision
                existing.recall = result.recall
                existing.f1_score = result.f1_score
                existing.latency_ms = result.latency_ms
                existing.cost_usd = result.cost_usd
                existing.success_rate = result.success_rate
                existing.user_satisfaction = result.user_satisfaction
                existing.reliability = result.reliability
                existing.security_score = result.security_score
                existing.composite_score = result.composite_score
                existing.updated_at = datetime.utcnow()
                entry = existing
            else:
                entry = LeaderboardEntry(
                    experiment_id=experiment_id,
                    rank=0,
                    **result.to_dict(),
                )
                db.add(entry)

            db.commit()

            # Re-rank all entries
            entries = db.query(LeaderboardEntry).order_by(
                LeaderboardEntry.composite_score.desc()
            ).all()
            for i, e in enumerate(entries):
                e.rank = i + 1
            db.commit()
            db.refresh(entry)

        return entry

    def get_leaderboard(self, limit: int = 20) -> list[LeaderboardEntry]:
        """Retrieve the current leaderboard."""
        with SessionLocal() as db:
            return (
                db.query(LeaderboardEntry)
                .order_by(LeaderboardEntry.rank.asc())
                .limit(limit)
                .all()
            )

    def store_evaluation(
        self,
        experiment_id: str,
        metric_name: str,
        value_before: float | None,
        value_after: float | None,
    ) -> Evaluation:
        """Store a single metric evaluation."""
        delta = None
        if value_before is not None and value_after is not None:
            delta = value_after - value_before

        ev = Evaluation(
            experiment_id=experiment_id,
            metric_name=metric_name,
            value_before=value_before,
            value_after=value_after,
            delta=delta,
        )
        with SessionLocal() as db:
            db.add(ev)
            db.commit()
            db.refresh(ev)
        return ev

    @staticmethod
    def _compute_composite(result: EvaluationResult) -> float:
        """Compute a weighted composite score (0-1) from all metrics.

        Trade-offs: accuracy and f1 are most important. Lower latency and cost
        are better, so they are inverted.
        """
        weights = {
            "accuracy": 0.20,
            "f1_score": 0.20,
            "success_rate": 0.15,
            "reliability": 0.15,
            "user_satisfaction": 0.10,
            "security_score": 0.10,
            "latency_norm": 0.05,
            "cost_norm": 0.05,
        }

        # Normalize latency and cost to [0,1] scale where lower is better.
        # Using sigmoid-like normalization; actual thresholds should be tuned.
        latency_norm = np.exp(-result.latency_ms / 1000.0)  # 1s -> 0.37
        cost_norm = np.exp(-result.cost_usd / 0.1)  # $0.10 -> 0.37

        composite = (
            weights["accuracy"] * result.accuracy
            + weights["f1_score"] * result.f1_score
            + weights["success_rate"] * result.success_rate
            + weights["reliability"] * result.reliability
            + weights["user_satisfaction"] * result.user_satisfaction
            + weights["security_score"] * result.security_score
            + weights["latency_norm"] * latency_norm
            + weights["cost_norm"] * cost_norm
        )
        return min(composite, 1.0)
