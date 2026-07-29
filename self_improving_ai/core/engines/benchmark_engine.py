"""
Benchmark Engine

Runs standardized performance benchmarks on experiments.
Tracks benchmark history for comparison.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable

import structlog
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.engines.base import BaseEngine
from core.models import Benchmark, Experiment

logger = structlog.get_logger(__name__)


class BenchmarkEngine(BaseEngine):
    """Runs and tracks benchmarks across experiments."""

    name = "benchmark_engine"

    _benchmarks: dict[str, Callable] = {}

    def register_benchmark(
        self, name: str, fn: Callable[[], dict[str, Any]]
    ) -> None:
        """Register a benchmark function by name."""
        self._benchmarks[name] = fn
        logger.info("benchmark.registered", name=name)

    def run_benchmark(
        self,
        experiment: Experiment,
        benchmark_name: str,
        input_data: dict[str, Any] | None = None,
    ) -> Benchmark:
        """Run a single named benchmark and record the result."""
        fn = self._benchmarks.get(benchmark_name)
        if fn is None:
            raise ValueError(f"Unknown benchmark: {benchmark_name}")

        logger.info("benchmark.running", name=benchmark_name, experiment=experiment.id)
        start = time.monotonic()

        try:
            result = fn(**(input_data or {}))
        except Exception as exc:
            logger.error("benchmark.failed", name=benchmark_name, error=str(exc))
            result = {"error": str(exc), "score": 0.0}

        elapsed = (time.monotonic() - start) * 1000
        self._record_call(elapsed, result.get("score", 0) > 0)

        benchmark = Benchmark(
            experiment_id=experiment.id,
            benchmark_name=benchmark_name,
            score=result.get("score", 0.0),
            max_score=result.get("max_score", 100.0),
            details={**result, "latency_ms": elapsed},
        )

        with SessionLocal() as db:
            db.add(benchmark)
            db.commit()
            db.refresh(benchmark)

        logger.info(
            "benchmark.completed",
            name=benchmark_name,
            score=benchmark.score,
            latency_ms=elapsed,
        )
        return benchmark

    def run_all_benchmarks(
        self,
        experiment: Experiment,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Benchmark]:
        """Run all registered benchmarks against an experiment."""
        results = {}
        for name in self._benchmarks:
            results[name] = self.run_benchmark(experiment, name, input_data)
        return results

    def compare_with_history(
        self,
        experiment: Experiment,
        benchmark_name: str,
    ) -> dict[str, Any]:
        """Compare current benchmark results with historical baselines."""
        with SessionLocal() as db:
            current = (
                db.query(Benchmark)
                .filter(
                    Benchmark.experiment_id == experiment.id,
                    Benchmark.benchmark_name == benchmark_name,
                )
                .order_by(Benchmark.timestamp.desc())
                .first()
            )

            historical = (
                db.query(Benchmark)
                .filter(Benchmark.benchmark_name == benchmark_name)
                .filter(Benchmark.experiment_id != experiment.id)
                .order_by(Benchmark.timestamp.desc())
                .limit(100)
                .all()
            )

        if not historical:
            return {"current": current.score if current else None, "historical_avg": None}

        hist_scores = [h.score for h in historical]
        return {
            "current_score": current.score if current else None,
            "historical_avg": sum(hist_scores) / len(hist_scores),
            "historical_min": min(hist_scores),
            "historical_max": max(hist_scores),
            "historical_count": len(hist_scores),
            "percentile": sum(1 for s in hist_scores if s <= (current.score if current else 0))
            / len(hist_scores)
            if current
            else 0,
        }

    def get_history(
        self, benchmark_name: str, limit: int = 50
    ) -> list[Benchmark]:
        """Retrieve benchmark run history."""
        with SessionLocal() as db:
            return (
                db.query(Benchmark)
                .filter(Benchmark.benchmark_name == benchmark_name)
                .order_by(Benchmark.timestamp.desc())
                .limit(limit)
                .all()
            )

    # ------------------------------------------------------------------
    # Standard benchmarks
    # ------------------------------------------------------------------

    @staticmethod
    def benchmark_latency(num_iterations: int = 100) -> dict[str, Any]:
        """Measure raw system latency under load."""
        times = []
        for _ in range(num_iterations):
            t0 = time.perf_counter()
            # Placeholder: actual work goes here
            time.sleep(0.001)
            times.append((time.perf_counter() - t0) * 1000)

        return {
            "score": 100.0,
            "max_score": 100.0,
            "avg_latency_ms": sum(times) / len(times),
            "p50_latency_ms": sorted(times)[len(times) // 2],
            "p95_latency_ms": sorted(times)[int(len(times) * 0.95)],
            "p99_latency_ms": sorted(times)[int(len(times) * 0.99)],
            "iterations": num_iterations,
        }

    @staticmethod
    def benchmark_accuracy(
        test_cases: list[dict[str, Any]],
        evaluate_fn: Callable[[dict[str, Any]], bool],
    ) -> dict[str, Any]:
        """Run accuracy benchmark on a set of test cases."""
        correct = 0
        for tc in test_cases:
            if evaluate_fn(tc):
                correct += 1

        score = (correct / max(len(test_cases), 1)) * 100
        return {
            "score": score,
            "max_score": 100.0,
            "correct": correct,
            "total": len(test_cases),
            "accuracy": score / 100,
        }
