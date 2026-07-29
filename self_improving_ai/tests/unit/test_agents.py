"""Unit tests for all agents."""

import pytest
import asyncio

from core.agents.planning_agent import PlanningAgent
from core.agents.reflection_agent import ReflectionAgent
from core.agents.critic_agent import CriticAgent
from core.agents.research_agent import ResearchAgent
from core.agents.testing_agent import TestingAgent
from core.agents.deployment_agent import DeploymentAgent
from core.agents.monitoring_agent import MonitoringAgent
from core.agents.logging_agent import LoggingAgent
from core.agents.human_approval_agent import HumanApprovalAgent


def run_async(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


class TestPlanningAgent:
    @pytest.fixture
    def agent(self):
        return PlanningAgent()

    def test_decompose_improve_goal(self, agent):
        subtasks = agent._decompose("improve system performance", {})
        assert len(subtasks) > 0
        assert any("analyze" in s["name"] for s in subtasks)

    def test_decompose_deploy_goal(self, agent):
        subtasks = agent._decompose("deploy new version", {})
        assert any("canary" in s["name"] or "deploy" in s["name"] for s in subtasks)

    def test_estimate_resources(self, agent):
        tasks = [
            {"name": "step1"},
            {"name": "step2"},
            {"name": "step3"},
        ]
        resources = agent._estimate_resources(tasks)
        assert resources["num_steps"] == 3
        assert resources["estimated_latency_ms"] > 0

    def test_full_execution(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "test_plan",
            "goal": "improve accuracy",
            "context": {},
            "constraints": [],
        }))
        assert "plan" in result
        plan = result["plan"]
        assert "subtasks" in plan
        assert "risks" in plan


class TestReflectionAgent:
    @pytest.fixture
    def agent(self):
        return ReflectionAgent()

    def test_extract_failure_patterns(self, agent):
        executions = [
            {"status": "failed", "errors": [{"type": "TimeoutError", "message": "timeout"}]},
            {"status": "failed", "errors": [{"type": "ValueError", "message": "bad value"}]},
            {"status": "completed"},
        ]
        patterns = agent._extract_failure_patterns(executions, [])
        assert len(patterns) >= 2

    def test_full_execution(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "test_reflect",
            "executions": [
                {"status": "completed", "latency_ms": 100},
                {"status": "failed", "errors": [{"type": "TimeoutError"}]},
            ],
            "observations": [],
        }))
        assert "reflection" in result
        assert "improvement_ideas" in result["reflection"]


class TestCriticAgent:
    @pytest.fixture
    def agent(self):
        return CriticAgent()

    def test_check_correctness_mismatch(self, agent):
        correctness = agent._check_correctness({
            "output": "wrong",
            "expected": "right",
        })
        assert correctness["score"] < 1.0
        assert len(correctness["issues"]) > 0

    def test_detect_hallucinations_numbers(self, agent):
        hallucinations = agent._detect_hallucinations({
            "output": "The year is 2024 and the total is 9999",
            "source_data": "This is the source text for 2024 analysis",
        })
        assert hallucinations["score"] < 1.0
        assert len(hallucinations["flags"]) > 0

    def test_full_execution(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "test_critique",
            "content": {
                "output": "The answer is 42.",
                "expected": "The answer is 42.",
                "source_data": "source text about 42",
            },
            "criteria": ["clarity", "completeness"],
        }))
        assert "critique" in result
        assert result["critique"]["verdict"] in ("ACCEPT", "REVISE")


class TestResearchAgent:
    @pytest.fixture
    def agent(self):
        return ResearchAgent()

    def test_full_execution(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "test_research",
            "query": "What is AI?",
            "sources": [
                {"content": "AI is artificial intelligence.", "source": "wiki"},
                {"content": "Machine learning is a subset of AI.", "source": "blog"},
            ],
        }))
        assert "result" in result
        assert "synthesis" in result["result"]
        assert "key_facts" in result["result"]


class TestTestingAgent:
    @pytest.fixture
    def agent(self):
        return TestingAgent()

    def test_security_tests_detect_secrets(self, agent):
        result = agent._run_security_tests({
            "output": "Here is my api_key: sk-1234567890abcdef"
        })
        assert result["passed"] == 0
        assert len(result["results"]) > 0

    def test_security_tests_clean_output(self, agent):
        result = agent._run_security_tests({
            "output": "The answer is 42. No secrets here."
        })
        assert result["passed"] == 1

    def test_regression_tests(self, agent):
        result = agent._run_regression_tests({
            "metrics_before": {"accuracy": 0.90, "f1_score": 0.88},
            "metrics_after": {"accuracy": 0.85, "f1_score": 0.83},
        })
        assert result["passed"] == 0

    def test_full_execution(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "test_run",
            "target": {"output": "clean output"},
            "tests": {},
            "test_suite": "security",
        }))
        assert "summary" in result
        assert result["summary"]["overall_pass"] is True


class TestDeploymentAgent:
    @pytest.fixture
    def agent(self):
        return DeploymentAgent()

    def test_validate_completed_experiment(self, agent):
        validation = agent._validate({
            "status": "completed",
            "regression_detected": False,
        })
        assert validation["valid"] is True

    def test_validate_reject_regression(self, agent):
        validation = agent._validate({
            "status": "completed",
            "regression_detected": True,
        })
        assert validation["valid"] is False

    def test_canary_deploy(self, agent):
        result = agent._deploy_canary({"id": "exp1", "canary_percentage": 10})
        assert result["success"] is True
        assert result["method"] == "canary"
        assert result["canary_percentage"] == 10

    def test_create_checkpoint(self, agent):
        checkpoint = agent._create_checkpoint({"id": "exp123"})
        assert checkpoint.startswith("ckpt_exp123_")


class TestMonitoringAgent:
    @pytest.fixture
    def agent(self):
        return MonitoringAgent()

    def test_healthy_system(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "monitor_1",
            "metrics": {
                "failure_rate": 0.01,
                "latency_p95_ms": 100,
                "cost_per_hour_usd": 0.10,
                "error_rate": 0.005,
                "user_satisfaction": 4.5,
            },
        }))
        assert result["status"] == "healthy"

    def test_critical_system(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "monitor_2",
            "metrics": {
                "failure_rate": 0.15,
                "latency_p95_ms": 8000,
                "cost_per_hour_usd": 2.00,
                "error_rate": 0.05,
                "user_satisfaction": 2.0,
            },
        }))
        assert result["status"] == "critical"
        assert len(result["alerts"]) > 0


class TestHumanApprovalAgent:
    @pytest.fixture
    def agent(self):
        return HumanApprovalAgent()

    def test_request_approval(self, agent):
        req = agent.request_approval(
            experiment_id="exp_1",
            experiment_name="Test Experiment",
            details={"improvement": 0.10},
            risk_level="minor",
        )
        assert req["status"] == "pending"
        assert req["risk_level"] == "minor"
        assert "approval_id" in req

    def test_approve_request(self, agent):
        req = agent.request_approval(
            experiment_id="exp_2",
            experiment_name="Test",
            details={},
        )
        approved = agent.approve(req["approval_id"], reviewer="admin", comment="LGTM")
        assert approved["status"] == "approved"
        assert len(approved["reviewers"]) == 1

    def test_reject_request(self, agent):
        req = agent.request_approval(
            experiment_id="exp_3",
            experiment_name="Test",
            details={},
        )
        rejected = agent.reject(req["approval_id"], reviewer="admin", reason="Not ready")
        assert rejected["status"] == "rejected"

    def test_check_status_not_requested(self, agent):
        status = agent.check_status("nonexistent")
        assert status["status"] == "not_requested"

    def test_auto_approve(self, agent):
        req = agent.request_approval(
            experiment_id="exp_auto",
            experiment_name="Auto Test",
            details={"actual_improvement": 0.02},
            risk_level="minor",
            auto_approve_threshold=0.05,
        )
        assert req["status"] == "approved"
        assert req.get("auto_approved") is True

    def test_get_pending(self, agent):
        agent.request_approval("exp_p1", "Pending 1", {})
        agent.request_approval("exp_p2", "Pending 2", {})
        pending = agent.get_pending()
        assert len(pending) == 2


class TestLoggingAgent:
    @pytest.fixture
    def agent(self):
        return LoggingAgent()

    def test_log_event(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "log_1",
            "event_type": "test_event",
            "event_data": {"key": "value"},
            "level": "INFO",
        }))
        assert result["logged"] is True

    def test_log_error(self, agent):
        result = run_async(agent.execute_with_trace({
            "task_id": "log_err",
            "event_type": "system_error",
            "event_data": {"error": "test error"},
            "level": "ERROR",
        }))
        assert result["logged"] is True
