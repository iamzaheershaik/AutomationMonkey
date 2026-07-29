# Self-Improving AI System

A production-grade AI platform that continuously optimizes its own prompts, workflows, tools, reasoning strategies, and code based on measurable performance. The system behaves like an AI engineering team rather than a single chatbot.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                 Self-Improving AI System                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  │
│  │ Observe │→│ Analyze │→│Generate │→│Experiment │  │
│  └─────────┘  └─────────┘  └─────────┘  └──────────┘  │
│       ↑                                         │       │
│       │                                    ┌────↓────┐  │
│       │                                    │Evaluate │  │
│       │                                    └────┬────┘  │
│       │                                         │       │
│  ┌────┴────┐  ┌─────────┐  ┌─────────┐  ┌─────↓─────┐ │
│  │ Monitor │←─│ Deploy  │←─│ Decide  │←─│ Compare   │ │
│  └─────────┘  └─────────┘  └─────────┘  └───────────┘ │
│                                                         │
│  ── Engines ──────────────────────────────────          │
│  • Observation Engine    • Memory Engine                │
│  • Evaluation Engine     • Experiment Engine            │
│  • Benchmark Engine      • Prompt Optimizer             │
│  • Tool Optimizer        • Workflow Optimizer           │
│                                                         │
│  ── Agents ───────────────────────────────────          │
│  • Planning    • Reflection  • Critic                   │
│  • Research    • Testing     • Deployment               │
│  • Monitoring  • Logging     • Human Approval           │
└─────────────────────────────────────────────────────────┘
```

## Improvement Loop

1. **Observe** — Collect user interactions, tool usage, errors, latency, costs, feedback
2. **Analyze** — Detect failure patterns, bottlenecks, weaknesses, expensive operations
3. **Generate** — Create multiple alternative improvement proposals
4. **Experiment** — Run controlled A/B tests in isolated branches
5. **Evaluate** — Measure accuracy, precision, recall, latency, cost, success rate
6. **Decide** — Accept only if ALL conditions: higher accuracy, lower/same cost, no regression, security passes, tests pass
7. **Deploy** — Canary releases with rollback support and feature flags
8. **Monitor** — Continue measuring performance, then repeat

## Quick Start

```bash
# Install
cd self_improving_ai
pip install -e ".[dev]"

# Initialize database
python -m self_improving_ai --init-db

# Start API server
python -m self_improving_ai --port 8000

# Run the continuous improvement loop
python -m self_improving_ai --loop

# Run tests
pytest tests/ -v

# Docker
docker-compose up -d
```

## Project Structure

```
self_improving_ai/
├── config/              # Settings & configuration
├── core/
│   ├── database.py      # SQLAlchemy engine & session
│   ├── models.py        # All database models
│   ├── engines/         # 8 specialized engines
│   │   ├── observation_engine.py
│   │   ├── memory_engine.py
│   │   ├── evaluation_engine.py
│   │   ├── experiment_engine.py
│   │   ├── benchmark_engine.py
│   │   ├── prompt_optimizer.py
│   │   ├── tool_optimizer.py
│   │   └── workflow_optimizer.py
│   └── agents/          # 9 specialized agents
│       ├── planning_agent.py
│       ├── reflection_agent.py
│       ├── critic_agent.py
│       ├── research_agent.py
│       ├── testing_agent.py
│       ├── deployment_agent.py
│       ├── monitoring_agent.py
│       ├── logging_agent.py
│       └── human_approval_agent.py
├── api/                 # FastAPI application
│   └── routes/          # REST API endpoints
├── orchestrator.py      # Continuous improvement loop
├── tests/               # Comprehensive test suite
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── stress/
├── observability/       # Prometheus + Grafana configs
├── .github/workflows/   # CI/CD pipeline
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | System status with engine health |
| POST | `/api/v1/observations/` | Record observation |
| GET | `/api/v1/observations/failure-rate` | Get failure rate |
| GET | `/api/v1/experiments/` | List experiments |
| POST | `/api/v1/experiments/` | Create experiment |
| POST | `/api/v1/experiments/{id}/check-deployable` | Check deployability |
| GET | `/api/v1/evaluations/leaderboard` | Get leaderboard |
| POST | `/api/v1/evaluations/` | Evaluate predictions |
| GET | `/api/v1/agents/` | List agents |
| POST | `/api/v1/agents/{name}/execute` | Execute agent |
| POST | `/api/v1/prompts/` | Create prompt |
| GET | `/api/v1/prompts/` | List prompts |
| POST | `/api/v1/tools/` | Register tool |
| GET | `/api/v1/tools/` | List tools |
| POST | `/api/v1/workflows/` | Create workflow |
| GET | `/api/v1/workflows/` | List workflows |
| POST | `/api/v1/approval/request` | Request approval |
| POST | `/api/v1/approval/{id}/approve` | Approve |
| POST | `/api/v1/approval/{id}/reject` | Reject |

## Safety Guarantees

- **Never** delete production code automatically
- **Never** deploy failed experiments
- **Never** ignore regression
- **Never** bypass approval policies
- **Always** create rollback checkpoints

## License

MIT
