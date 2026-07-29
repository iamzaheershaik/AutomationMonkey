"""End-to-end tests for the full improvement cycle via API."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from api import app
from config.settings import ensure_directories
from core.database import init_db
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

# Initialize engines globally for TestClient (no lifespan)
ensure_directories()
init_db()

import api as api_module
api_module._observation_engine = ObservationEngine()
api_module._memory_engine = MemoryEngine()
api_module._evaluation_engine = EvaluationEngine()
api_module._experiment_engine = ExperimentEngine()
api_module._benchmark_engine = BenchmarkEngine()
api_module._prompt_optimizer = PromptOptimizer()
api_module._tool_optimizer = ToolOptimizer()
api_module._workflow_optimizer = WorkflowOptimizer()

for eng in [
    api_module._observation_engine,
    api_module._memory_engine,
    api_module._evaluation_engine,
    api_module._experiment_engine,
    api_module._benchmark_engine,
    api_module._prompt_optimizer,
    api_module._tool_optimizer,
    api_module._workflow_optimizer,
]:
    eng.start()

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup():
    """Initialize database and clear state between tests."""
    init_db()
    from core.database import SessionLocal
    from core.models import PromptVersion, ToolVersion, WorkflowVersion
    with SessionLocal() as db:
        db.query(PromptVersion).delete()
        db.query(ToolVersion).delete()
        db.query(WorkflowVersion).delete()
        db.commit()


class TestHealthEndpoints:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_system_status(self):
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "engines" in data


class TestObservationEndpoints:
    def test_record_observation(self):
        response = client.post(
            "/api/v1/observations/",
            params={
                "observation_type": "user_interaction",
                "session_id": "e2e_test",
                "success": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "observation_id" in data

    def test_get_failure_rate(self):
        response = client.get("/api/v1/observations/failure-rate")
        assert response.status_code == 200


class TestExperimentEndpoints:
    def test_create_experiment(self):
        response = client.post(
            "/api/v1/experiments/",
            params={
                "name": "E2E Test Experiment",
                "description": "End-to-end test",
                "improvement_type": "prompt",
                "hypothesis": "Test hypothesis",
                "expected_improvement": 0.10,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "proposed"
        assert "experiment_id" in data

    def test_list_experiments(self):
        # Create one first
        client.post(
            "/api/v1/experiments/",
            params={
                "name": "List Test",
                "improvement_type": "prompt",
                "hypothesis": "Test",
            },
        )
        response = client.get("/api/v1/experiments/")
        assert response.status_code == 200
        data = response.json()
        assert "experiments" in data


class TestEvaluationEndpoints:
    def test_evaluate(self):
        response = client.post(
            "/api/v1/evaluations/",
            json={
                "y_true": ["a", "b", "c"],
                "y_pred": ["a", "b", "c"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["accuracy"] == 1.0

    def test_leaderboard(self):
        response = client.get("/api/v1/evaluations/leaderboard")
        assert response.status_code == 200


class TestAgentEndpoints:
    def test_list_agents(self):
        response = client.get("/api/v1/agents/")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data

    def test_create_plan(self):
        response = client.post(
            "/api/v1/agents/planning/plan",
            params={"goal": "improve system accuracy"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "plan" in data

    def test_reflect(self):
        response = client.post(
            "/api/v1/agents/reflection/reflect",
            json={
                "executions": [
                    {"status": "completed", "latency_ms": 100},
                    {"status": "failed", "errors": [{"type": "TimeoutError"}]},
                ],
            },
        )
        assert response.status_code == 200

    def test_critique(self):
        response = client.post(
            "/api/v1/agents/critic/critique",
            json={
                "content": {
                    "output": "The answer is 42.",
                    "expected": "The answer is 42.",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "critique" in data

    def test_request_approval(self):
        response = client.post(
            "/api/v1/agents/approval/request",
            params={
                "experiment_id": "exp_e2e",
                "experiment_name": "E2E Experiment",
                "risk_level": "minor",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "approval_id" in data

    def test_monitoring_check(self):
        response = client.post(
            "/api/v1/agents/monitoring/check",
            json={
                "metrics": {
                    "failure_rate": 0.01,
                    "latency_p95_ms": 100,
                    "cost_per_hour_usd": 0.05,
                    "error_rate": 0.01,
                    "user_satisfaction": 4.5,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_run_tests(self):
        response = client.post(
            "/api/v1/agents/testing/run",
            json={
                "target": {"output": "clean output"},
                "test_suite": "security",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["overall_pass"] is True


class TestPromptEndpoints:
    def test_create_prompt(self):
        response = client.post(
            "/api/v1/prompts/",
            params={
                "name": "e2e_prompt",
                "version": "1.0.0",
                "template": "You are a helpful assistant. Answer: {{query}}",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "e2e_prompt"

    def test_list_prompts(self):
        response = client.get("/api/v1/prompts/")
        assert response.status_code == 200


class TestToolEndpoints:
    def test_register_tool(self):
        response = client.post(
            "/api/v1/tools/",
            params={
                "name": "e2e_tool",
                "version": "1.0.0",
                "description": "Test tool",
            },
        )
        assert response.status_code == 200

    def test_list_tools(self):
        response = client.get("/api/v1/tools/")
        assert response.status_code == 200


class TestWorkflowEndpoints:
    def test_create_workflow(self):
        response = client.post(
            "/api/v1/workflows/",
            params={
                "name": "e2e_workflow",
                "description": "Test workflow",
            },
            json={"steps": {"sequence": ["step1", "step2", "step3"]}},
        )
        assert response.status_code == 200

    def test_list_workflows(self):
        response = client.get("/api/v1/workflows/")
        assert response.status_code == 200
