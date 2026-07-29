"""Unit tests for core database and models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base, init_db
from core.models import (
    Benchmark,
    Deployment,
    Evaluation,
    Experiment,
    ExperimentStatus,
    FailureCategory,
    ImprovementType,
    MemoryEntry,
    Observation,
    ObservationType,
    PromptVersion,
    ToolVersion,
    WorkflowVersion,
)


@pytest.fixture(scope="module")
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a fresh session for each test."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestObservationModel:
    def test_create_observation(self, db_session):
        obs = Observation(
            observation_type=ObservationType.USER_INTERACTION,
            session_id="test_session",
            success=True,
        )
        db_session.add(obs)
        db_session.commit()

        retrieved = db_session.query(Observation).filter(Observation.id == obs.id).first()
        assert retrieved is not None
        assert retrieved.observation_type == ObservationType.USER_INTERACTION
        assert retrieved.success is True

    def test_observation_with_failure(self, db_session):
        obs = Observation(
            observation_type=ObservationType.ERROR,
            success=False,
            failure_category=FailureCategory.HALLUCINATION,
            error_message="Test hallucination error",
        )
        db_session.add(obs)
        db_session.commit()

        retrieved = db_session.query(Observation).filter(Observation.id == obs.id).first()
        assert retrieved.failure_category == FailureCategory.HALLUCINATION
        assert "hallucination" in retrieved.error_message

    def test_observation_with_metrics(self, db_session):
        obs = Observation(
            observation_type=ObservationType.TOOL_USAGE,
            latency_ms=150.5,
            cost_usd=0.003,
            tokens_in=100,
            tokens_out=50,
        )
        db_session.add(obs)
        db_session.commit()

        retrieved = db_session.query(Observation).filter(Observation.id == obs.id).first()
        assert retrieved.latency_ms == 150.5
        assert retrieved.cost_usd == 0.003
        assert retrieved.tokens_in == 100
        assert retrieved.tokens_out == 50


class TestExperimentModel:
    def test_create_experiment(self, db_session):
        exp = Experiment(
            name="Test Experiment",
            description="A test",
            improvement_type=ImprovementType.PROMPT.value,
            base_version="1.0.0",
            experiment_branch="exp/test-abc123",
            status=ExperimentStatus.PROPOSED.value,
        )
        db_session.add(exp)
        db_session.commit()

        retrieved = db_session.query(Experiment).filter(Experiment.id == exp.id).first()
        assert retrieved.name == "Test Experiment"
        assert retrieved.status == ExperimentStatus.PROPOSED.value

    def test_experiment_lifecycle(self, db_session):
        exp = Experiment(
            name="Lifecycle Test",
            improvement_type=ImprovementType.WORKFLOW.value,
            base_version="1.0.0",
            experiment_branch="exp/lifecycle-xyz",
        )
        db_session.add(exp)
        db_session.commit()

        exp.status = ExperimentStatus.RUNNING.value
        db_session.commit()
        assert exp.status == ExperimentStatus.RUNNING.value

        exp.status = ExperimentStatus.COMPLETED.value
        exp.actual_improvement = 0.15
        db_session.commit()
        assert exp.status == ExperimentStatus.COMPLETED.value
        assert exp.actual_improvement == 0.15


class TestMemoryEntryModel:
    def test_short_term_memory(self, db_session):
        from datetime import datetime, timedelta
        entry = MemoryEntry(
            memory_type="short_term",
            key="st:session_1:context",
            value={"user_input": "hello"},
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(entry)
        db_session.commit()

        retrieved = db_session.query(MemoryEntry).filter(MemoryEntry.id == entry.id).first()
        assert retrieved.memory_type == "short_term"
        assert retrieved.value == {"user_input": "hello"}

    def test_long_term_memory(self, db_session):
        entry = MemoryEntry(
            memory_type="long_term",
            key="lt:skill_python",
            value={"skill": "python", "proficiency": 0.9},
            importance=0.8,
        )
        db_session.add(entry)
        db_session.commit()

        retrieved = db_session.query(MemoryEntry).filter(MemoryEntry.id == entry.id).first()
        assert retrieved.importance == 0.8


class TestPromptVersionModel:
    def test_create_prompt_version(self, db_session):
        prompt = PromptVersion(
            name="system_prompt",
            version="1.0.0",
            template="You are a helpful assistant.",
            model="gpt-4",
        )
        db_session.add(prompt)
        db_session.commit()

        retrieved = db_session.query(PromptVersion).filter(PromptVersion.id == prompt.id).first()
        assert retrieved.name == "system_prompt"
        assert retrieved.model == "gpt-4"


class TestEvaluationModel:
    def test_create_evaluation(self, db_session):
        # First create an experiment
        exp = Experiment(
            name="Eval Test",
            improvement_type=ImprovementType.PROMPT.value,
            base_version="1.0.0",
            experiment_branch="exp/eval-test",
        )
        db_session.add(exp)
        db_session.commit()

        evaluation = Evaluation(
            experiment_id=exp.id,
            metric_name="accuracy",
            value_before=0.80,
            value_after=0.90,
            delta=0.10,
            passed=True,
        )
        db_session.add(evaluation)
        db_session.commit()

        retrieved = db_session.query(Evaluation).filter(Evaluation.id == evaluation.id).first()
        assert retrieved.metric_name == "accuracy"
        assert retrieved.delta == 0.10
        assert retrieved.passed is True
