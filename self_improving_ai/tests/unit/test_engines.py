"""Unit tests for core engines."""

import pytest

from core.engines.base import BaseEngine, EngineMetrics
from core.engines.evaluation_engine import EvaluationEngine, EvaluationResult
from core.engines.experiment_engine import ExperimentEngine
from core.engines.observation_engine import ObservationEngine
from core.models import ExperimentStatus, ImprovementType, ObservationType


class TestEngineMetrics:
    def test_initial_metrics(self):
        metrics = EngineMetrics()
        assert metrics.calls == 0
        assert metrics.errors == 0
        assert metrics.avg_latency_ms == 0.0

    def test_metrics_update(self):
        metrics = EngineMetrics()
        metrics.calls = 10
        metrics.errors = 2
        metrics.total_latency_ms = 1000.0
        assert metrics.avg_latency_ms == 100.0
        assert metrics.success_rate == 0.8


class TestBaseEngine:
    def test_engine_lifecycle(self):
        engine = BaseEngine()
        engine.name = "test_engine"
        engine.start()
        assert engine.health_check() is True
        engine.stop()

    def test_record_call(self):
        engine = BaseEngine()
        engine.name = "test_engine"
        engine._record_call(100.0, success=True)
        engine._record_call(200.0, success=False)
        assert engine._metrics.calls == 2
        assert engine._metrics.errors == 1
        assert engine._metrics.success_rate == 0.5
        assert engine._metrics.avg_latency_ms == 150.0

    def test_get_metrics(self):
        engine = BaseEngine()
        engine.name = "test_engine"
        engine._record_call(50.0)
        metrics = engine.get_metrics()
        assert metrics["engine"] == "test_engine"
        assert metrics["calls"] == 1
        assert "avg_latency_ms" in metrics


class TestEvaluationEngine:
    @pytest.fixture
    def eval_engine(self):
        return EvaluationEngine()

    def test_evaluate_perfect(self, eval_engine):
        y_true = ["a", "b", "c", "d"]
        y_pred = ["a", "b", "c", "d"]
        result = eval_engine.evaluate(y_true, y_pred)
        assert result.accuracy == 1.0
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1_score == 1.0

    def test_evaluate_partial(self, eval_engine):
        y_true = ["a", "a", "b", "b"]
        y_pred = ["a", "b", "a", "b"]
        result = eval_engine.evaluate(y_true, y_pred)
        assert result.accuracy == 0.5
        assert 0.0 <= result.f1_score <= 1.0

    def test_evaluate_all_wrong(self, eval_engine):
        y_true = ["a", "a", "a"]
        y_pred = ["b", "b", "b"]
        result = eval_engine.evaluate(y_true, y_pred)
        assert result.accuracy == 0.0

    def test_composite_score(self, eval_engine):
        result = EvaluationResult(
            accuracy=0.9,
            precision=0.9,
            recall=0.9,
            f1_score=0.9,
            success_rate=0.95,
            reliability=0.95,
            user_satisfaction=4.5,
            security_score=0.95,
            latency_ms=100,
            cost_usd=0.001,
        )
        composite = eval_engine._compute_composite(result)
        assert 0.0 <= composite <= 1.0
        assert composite > 0.5

    def test_to_dict(self, eval_engine):
        result = EvaluationResult(accuracy=0.9, f1_score=0.85)
        d = result.to_dict()
        assert d["accuracy"] == 0.9
        assert d["f1_score"] == 0.85
        assert "composite_score" in d


class TestExperimentEngine:
    @pytest.fixture
    def exp_engine(self):
        return ExperimentEngine()

    def test_propose_experiment(self, exp_engine):
        exp = exp_engine.propose_experiment(
            name="Test Proposal",
            description="Testing proposal flow",
            improvement_type=ImprovementType.PROMPT.value,
            hypothesis="Better prompts yield better results",
            expected_improvement=0.10,
            proposed_changes={"prompt_version": "2.0.0"},
        )
        assert exp.name == "Test Proposal"
        assert exp.status == ExperimentStatus.PROPOSED.value
        assert exp.experiment_branch.startswith("exp/test-proposal-")

    def test_experiment_deployable_check_failures(self, exp_engine):
        exp = exp_engine.propose_experiment(
            name="Deployable Test",
            description="Test",
            improvement_type=ImprovementType.TOOL.value,
            hypothesis="Test",
            expected_improvement=0.10,
            proposed_changes={},
        )
        is_deployable, failures = exp_engine.is_deployable(exp)
        assert not is_deployable
        assert len(failures) > 0

    def test_is_deployable_with_good_metrics(self, exp_engine):
        exp = exp_engine.propose_experiment(
            name="Good Test",
            description="Test",
            improvement_type=ImprovementType.PROMPT.value,
            hypothesis="Test",
            expected_improvement=0.10,
            proposed_changes={},
        )
        exp.status = ExperimentStatus.COMPLETED.value
        exp.regression_detected = False
        exp.actual_improvement = 0.15
        exp.metrics_before = {"accuracy": 0.80, "cost_usd": 0.01}
        exp.metrics_after = {"accuracy": 0.90, "cost_usd": 0.009}

        is_deployable, failures = exp_engine.is_deployable(exp)
        assert is_deployable, f"Failures: {failures}"

    def test_deployable_fails_on_regression(self, exp_engine):
        exp = exp_engine.propose_experiment(
            name="Regression Test",
            description="Test",
            improvement_type=ImprovementType.PROMPT.value,
            hypothesis="Test",
            expected_improvement=0.10,
            proposed_changes={},
        )
        exp.status = ExperimentStatus.COMPLETED.value
        exp.regression_detected = True
        is_deployable, failures = exp_engine.is_deployable(exp)
        assert not is_deployable

    def test_should_reject_experiment(self, exp_engine):
        exp = exp_engine.propose_experiment(
            name="Reject Test",
            description="Test",
            improvement_type=ImprovementType.PROMPT.value,
            hypothesis="Test",
            expected_improvement=0.10,
            proposed_changes={},
        )
        rejected = exp_engine.reject_experiment(exp, "Not good enough")
        assert rejected.status == ExperimentStatus.REJECTED.value


class TestObservationEngine:
    @pytest.fixture
    def obs_engine(self):
        return ObservationEngine()

    def test_record_user_interaction(self, obs_engine):
        obs = obs_engine.record_observation(
            observation_type=ObservationType.USER_INTERACTION,
            session_id="sess_1",
            task_id="task_1",
            success=True,
            latency_ms=200.0,
        )
        assert obs is not None
        assert obs.observation_type == ObservationType.USER_INTERACTION
        assert obs.success is True

    def test_record_error(self, obs_engine):
        obs = obs_engine.record_observation(
            observation_type=ObservationType.ERROR,
            success=False,
            error_message="Division by zero",
        )
        assert obs.success is False
        assert "Division by zero" in obs.error_message

    def test_record_with_metrics(self, obs_engine):
        obs = obs_engine.record_observation(
            observation_type=ObservationType.TOOL_USAGE,
            cost_usd=0.005,
            tokens_in=250,
            tokens_out=100,
        )
        assert obs.cost_usd == 0.005
        assert obs.tokens_in == 250

    def test_get_session_observations(self, obs_engine):
        obs_engine.record_observation(
            observation_type=ObservationType.USER_INTERACTION,
            session_id="sess_test",
            success=True,
        )
        results = obs_engine.get_session_observations("sess_test", limit=10)
        assert len(results) >= 1
        assert results[0].session_id == "sess_test"
