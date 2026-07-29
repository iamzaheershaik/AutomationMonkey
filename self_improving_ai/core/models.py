"""
Core data models for the Self-Improving AI System.

Covers:
- Observations (user interactions, tool usage, errors, latency, costs)
- Experiments & branches
- Benchmarks & evaluations
- Prompts, workflows, tools (versioned)
- Agents & their execution history
- Memory entries
- Deployment records
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database import Base


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _utcnow() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ObservationType(str, Enum):
    USER_INTERACTION = "user_interaction"
    TOOL_USAGE = "tool_usage"
    ERROR = "error"
    LATENCY = "latency"
    COST = "cost"
    TOKEN_USAGE = "token_usage"
    FAILURE = "failure"
    HUMAN_FEEDBACK = "human_feedback"
    SUCCESS = "success"


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"


class DeploymentStrategy(str, Enum):
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    FULL = "full"


class ImprovementType(str, Enum):
    PROMPT = "prompt"
    TOOL = "tool"
    WORKFLOW = "workflow"
    REASONING = "reasoning"
    MEMORY = "memory"
    CODE = "code"
    API = "api"
    UI = "ui"


class FailureCategory(str, Enum):
    HALLUCINATION = "hallucination"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    INCORRECT_OUTPUT = "incorrect_output"
    PARSE_ERROR = "parse_error"
    SECURITY = "security"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Observation Models
# ---------------------------------------------------------------------------


class Observation(Base):
    __tablename__ = "observations"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    observation_type: str = Column(String(32), nullable=False, index=True)
    session_id: str = Column(String(64), index=True)
    task_id: str = Column(String(24), index=True)
    timestamp: datetime = Column(DateTime, default=_utcnow, index=True)

    payload: dict = Column(JSON, default=dict)
    extra_data: dict = Column(JSON, default=dict)

    # Measured metrics
    latency_ms: float = Column(Float, nullable=True)
    cost_usd: float = Column(Float, nullable=True)
    tokens_in: int = Column(Integer, nullable=True)
    tokens_out: int = Column(Integer, nullable=True)

    # Success / Failure
    success: bool = Column(Boolean, nullable=True, index=True)
    failure_category: str = Column(String(32), nullable=True)
    error_message: str = Column(Text, nullable=True)
    stack_trace: str = Column(Text, nullable=True)

    # Human feedback
    human_rating: int = Column(Integer, nullable=True)  # 1-5
    human_comment: str = Column(Text, nullable=True)

    # Confidence
    model_confidence: float = Column(Float, nullable=True)


class ToolUsage(Base):
    __tablename__ = "tool_usages"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    observation_id: str = Column(String(24), ForeignKey("observations.id"), nullable=False)
    tool_name: str = Column(String(128), nullable=False, index=True)
    tool_version: str = Column(String(32), default="1.0.0")
    arguments: dict = Column(JSON, default=dict)
    result: dict = Column(JSON, default=dict)
    success: bool = Column(Boolean, default=True)
    latency_ms: float = Column(Float, nullable=True)
    cost_usd: float = Column(Float, nullable=True)
    tokens_in: int = Column(Integer, nullable=True)
    tokens_out: int = Column(Integer, nullable=True)
    timestamp: datetime = Column(DateTime, default=_utcnow)

    observation = relationship("Observation", backref="tool_usages")


# ---------------------------------------------------------------------------
# Experiment Models
# ---------------------------------------------------------------------------


class Experiment(Base):
    __tablename__ = "experiments"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    name: str = Column(String(256), nullable=False)
    description: str = Column(Text, default="")
    status: str = Column(String(32), default=ExperimentStatus.PROPOSED.value, index=True)
    improvement_type: str = Column(String(64), nullable=False)

    # Branching
    base_version: str = Column(String(64), nullable=False)
    experiment_branch: str = Column(String(128), unique=True, nullable=False)
    parent_experiment_id: str = Column(String(24), ForeignKey("experiments.id"), nullable=True)

    # Proposal
    hypothesis: str = Column(Text, default="")
    expected_improvement: float = Column(Float, default=0.0)
    proposed_changes: dict = Column(JSON, default=dict)

    # Results
    actual_improvement: float = Column(Float, nullable=True)
    metrics_before: dict = Column(JSON, default=dict)
    metrics_after: dict = Column(JSON, default=dict)
    regression_detected: bool = Column(Boolean, default=False)
    stability_score: float = Column(Float, nullable=True)
    extra_data: dict = Column(JSON, default=dict)

    # Timestamps
    created_at: datetime = Column(DateTime, default=_utcnow)
    started_at: datetime = Column(DateTime, nullable=True)
    completed_at: datetime = Column(DateTime, nullable=True)
    deployed_at: datetime = Column(DateTime, nullable=True)

    # Relationships
    parent = relationship("Experiment", remote_side="Experiment.id", backref="children")
    evaluations = relationship("Evaluation", backref="experiment", cascade="all, delete-orphan")
    benchmarks = relationship("Benchmark", backref="experiment", cascade="all, delete-orphan")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    experiment_id: str = Column(String(24), ForeignKey("experiments.id"), nullable=False)
    metric_name: str = Column(String(128), nullable=False)
    value_before: float = Column(Float, nullable=True)
    value_after: float = Column(Float, nullable=True)
    delta: float = Column(Float, nullable=True)
    p_value: float = Column(Float, nullable=True)
    sample_size: int = Column(Integer, default=0)
    passed: bool = Column(Boolean, nullable=True)
    timestamp: datetime = Column(DateTime, default=_utcnow)


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    experiment_id: str = Column(String(24), ForeignKey("experiments.id"), nullable=False)
    benchmark_name: str = Column(String(256), nullable=False)
    score: float = Column(Float, nullable=False)
    max_score: float = Column(Float, default=100.0)
    details: dict = Column(JSON, default=dict)
    timestamp: datetime = Column(DateTime, default=_utcnow)


# ---------------------------------------------------------------------------
# Versioned Artifacts (Prompts, Workflows, Tools)
# ---------------------------------------------------------------------------


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    name: str = Column(String(256), nullable=False, index=True)
    version: str = Column(String(32), nullable=False)
    template: str = Column(Text, nullable=False)
    variables: dict = Column(JSON, default=dict)
    model: str = Column(String(128), nullable=False)
    performance_score: float = Column(Float, default=0.0)
    usage_count: int = Column(Integer, default=0)
    success_rate: float = Column(Float, default=1.0)
    avg_latency_ms: float = Column(Float, default=0.0)
    avg_cost_usd: float = Column(Float, default=0.0)
    created_at: datetime = Column(DateTime, default=_utcnow)
    is_active: bool = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    name: str = Column(String(256), nullable=False, index=True)
    version: str = Column(String(32), nullable=False)
    steps: dict = Column(JSON, default=dict)
    description: str = Column(Text, default="")
    performance_score: float = Column(Float, default=0.0)
    usage_count: int = Column(Integer, default=0)
    success_rate: float = Column(Float, default=1.0)
    avg_latency_ms: float = Column(Float, default=0.0)
    avg_cost_usd: float = Column(Float, default=0.0)
    created_at: datetime = Column(DateTime, default=_utcnow)
    is_active: bool = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_workflow_name_version"),
    )


class ToolVersion(Base):
    __tablename__ = "tool_versions"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    name: str = Column(String(256), nullable=False, index=True)
    version: str = Column(String(32), nullable=False)
    description: str = Column(Text, default="")
    implementation: str = Column(Text, default="")
    signature: dict = Column(JSON, default=dict)
    performance_score: float = Column(Float, default=0.0)
    usage_count: int = Column(Integer, default=0)
    success_rate: float = Column(Float, default=1.0)
    avg_latency_ms: float = Column(Float, default=0.0)
    created_at: datetime = Column(DateTime, default=_utcnow)
    is_active: bool = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_tool_name_version"),
    )


# ---------------------------------------------------------------------------
# Memory Models
# ---------------------------------------------------------------------------


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    memory_type: str = Column(String(32), nullable=False, index=True)  # short_term, long_term, semantic, task
    key: str = Column(String(512), nullable=False)
    value: dict = Column(JSON, default=dict)
    embedding_id: str = Column(String(128), nullable=True)
    importance: float = Column(Float, default=0.5)
    access_count: int = Column(Integer, default=0)
    last_accessed: datetime = Column(DateTime, default=_utcnow)
    created_at: datetime = Column(DateTime, default=_utcnow)
    expires_at: datetime = Column(DateTime, nullable=True)
    tags: dict = Column(JSON, default=list)


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    agent_name: str = Column(String(128), nullable=False, index=True)
    agent_version: str = Column(String(32), default="1.0.0")
    task_id: str = Column(String(24), index=True)
    status: str = Column(String(32), default="started", index=True)
    input_data: dict = Column(JSON, default=dict)
    output_data: dict = Column(JSON, default=dict)
    steps: dict = Column(JSON, default=list)
    errors: dict = Column(JSON, default=list)
    latency_ms: float = Column(Float, nullable=True)
    cost_usd: float = Column(Float, nullable=True)
    tokens_used: int = Column(Integer, default=0)
    started_at: datetime = Column(DateTime, default=_utcnow)
    completed_at: datetime = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Deployment Models
# ---------------------------------------------------------------------------


class Deployment(Base):
    __tablename__ = "deployments"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    experiment_id: str = Column(String(24), ForeignKey("experiments.id"), nullable=False)
    strategy: str = Column(String(32), nullable=False)
    canary_percentage: int = Column(Integer, default=10)
    status: str = Column(String(32), default="pending", index=True)
    rollback_checkpoint: str = Column(String(128), nullable=True)
    deployed_at: datetime = Column(DateTime, default=_utcnow)
    rolled_back_at: datetime = Column(DateTime, nullable=True)
    rollback_reason: str = Column(Text, nullable=True)
    feature_flag: str = Column(String(128), nullable=True)
    deployment_log: dict = Column(JSON, default=dict)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard"

    id: str = Column(String(24), primary_key=True, default=_new_id)
    experiment_id: str = Column(String(24), ForeignKey("experiments.id"), nullable=False)
    rank: int = Column(Integer, nullable=False)
    accuracy: float = Column(Float, default=0.0)
    precision: float = Column(Float, default=0.0)
    recall: float = Column(Float, default=0.0)
    f1_score: float = Column(Float, default=0.0)
    latency_ms: float = Column(Float, default=0.0)
    cost_usd: float = Column(Float, default=0.0)
    success_rate: float = Column(Float, default=0.0)
    user_satisfaction: float = Column(Float, default=0.0)
    reliability: float = Column(Float, default=0.0)
    security_score: float = Column(Float, default=0.0)
    composite_score: float = Column(Float, default=0.0)
    updated_at: datetime = Column(DateTime, default=_utcnow)
