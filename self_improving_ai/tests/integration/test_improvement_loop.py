"""Integration tests for the end-to-end improvement loop."""

import asyncio
import pytest

from core.database import init_db
from core.engines import (
    BenchmarkEngine,
    EvaluationEngine,
    ExperimentEngine,
    MemoryEngine,
    ObservationEngine,
)
from core.models import ExperimentStatus, ImprovementType, ObservationType


def run_async(coro):
    return asyncio.run(coro)


class TestEndToEndImprovementFlow:
    """Integration test: full improvement cycle from proposal to evaluation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        init_db()

    def test_full_improvement_proposal_to_evaluation(self):
        """Test that an experiment goes through proposal -> evaluation correctly."""
        exp_engine = ExperimentEngine()
        eval_engine = EvaluationEngine()
        obs_engine = ObservationEngine()

        # 1. Observe: Record baseline
        obs_engine.record_observation(
            observation_type=ObservationType.USER_INTERACTION,
            session_id="integration_test",
            success=True,
        )

        # 2. Propose improvement
        experiment = exp_engine.propose_experiment(
            name="Integration Test Experiment",
            description="E2E test of the improvement loop",
            improvement_type=ImprovementType.PROMPT.value,
            hypothesis="Adding instructions improves accuracy by 10%",
            expected_improvement=0.10,
            proposed_changes={"prompt": "updated template"},
        )
        assert experiment.status == ExperimentStatus.PROPOSED.value

        # 3. Simulate experiment completion with good metrics
        experiment.status = ExperimentStatus.RUNNING.value
        exp_engine._save_state(experiment)

        experiment.status = ExperimentStatus.COMPLETED.value
        experiment.regression_detected = False
        experiment.actual_improvement = 0.12
        experiment.metrics_before = {"accuracy": 0.80, "cost_usd": 0.005}
        experiment.metrics_after = {"accuracy": 0.90, "cost_usd": 0.004}
        exp_engine._save_state(experiment)

        # 4. Check deployability
        is_deployable, failures = exp_engine.is_deployable(experiment)
        assert is_deployable, f"Should be deployable: {failures}"

        # 5. Evaluate and update leaderboard
        from core.engines.evaluation_engine import EvaluationResult
        result = EvaluationResult(
            accuracy=0.90,
            f1_score=0.88,
            success_rate=0.95,
            cost_usd=0.004,
        )
        entry = eval_engine.update_leaderboard(experiment.id, result)
        assert entry.experiment_id == experiment.id

        # 6. Verify leaderboard
        board = eval_engine.get_leaderboard()
        assert len(board) >= 1


class TestMemoryFlow:
    """Integration test: memory storage and retrieval."""

    @pytest.fixture(autouse=True)
    def setup(self):
        init_db()

    def test_store_and_recall(self):
        mem = MemoryEngine()

        mem.store_short_term("key1", {"data": "test1"}, session_id="sess_1")
        mem.store_long_term("key2", {"data": "test2"}, importance=0.8)
        mem.store_task("task_1", {"progress": "50%"})

        context = mem.recall_context(session_id="sess_1", task_id="task_1")
        assert len(context["short_term"]) >= 1
        assert len(context["task"]) >= 1
        assert context["short_term"][0]["data"] == "test1"

        entries = mem.recall("st:sess_1:key1", memory_type="short_term")
        assert len(entries) >= 1


class TestObservationToAnalysis:
    """Integration test: observing failures leading to analysis."""

    @pytest.fixture(autouse=True)
    def setup(self):
        init_db()

    def test_failure_rate_monitoring(self):
        obs_engine = ObservationEngine()

        # Simulate several failures
        for i in range(5):
            obs_engine.record_observation(
                observation_type=ObservationType.ERROR,
                session_id="analysis_test",
                success=False,
                error_message=f"Error {i}",
            )

        for i in range(10):
            obs_engine.record_observation(
                observation_type=ObservationType.USER_INTERACTION,
                session_id="analysis_test",
                success=True,
            )

        failure_rate = obs_engine.get_failure_rate(window_hours=24)
        assert failure_rate["failure_rate"] > 0


class TestOptimizerFlow:
    """Integration test: optimizer analysis and variant generation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        init_db()

    def test_prompt_analysis_and_variants(self):
        from core.engines.prompt_optimizer import PromptOptimizer
        from core.models import PromptVersion

        optimizer = PromptOptimizer()
        prompt = PromptVersion(
            name="test_prompt",
            version="1.0.0",
            template="Answer the following question: {{question}}",
            model="gpt-4",
        )

        analysis = optimizer.analyze_prompt(
            prompt,
            failure_cases=[
                {"failure_category": "hallucination", "input": "test"},
                {"failure_category": "hallucination", "input": "test2"},
            ],
            success_cases=[{"input": "test3"}],
        )

        assert analysis["failure_rate"] > 0
        assert len(analysis["suggestions"]) > 0

        variants = optimizer.generate_variants(prompt, analysis, num_variants=3)
        assert len(variants) <= 3
        assert len(variants) > 0

        for variant in variants:
            assert variant.name == prompt.name
            assert variant.version != prompt.version
