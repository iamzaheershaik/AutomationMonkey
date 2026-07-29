# Architecture Document

## System Architecture

```
                         ┌─────────────────────────┐
                         │    FastAPI REST API      │
                         │    /api/v1/*             │
                         └───────────┬─────────────┘
                                     │
                    ┌────────────────┼──────────────────┐
                    │                │                   │
              ┌─────▼─────┐   ┌─────▼─────┐    ┌──────▼──────┐
              │  Routes   │   │  Routes   │    │   Routes    │
              │ Observ.   │   │  Exp.     │    │   Agents    │
              └─────┬─────┘   └─────┬─────┘    └──────┬──────┘
                    │                │                   │
          ┌─────────▼────────────────▼───────────────────▼──────┐
          │                   Core Engines                       │
          │  ┌───────────┐ ┌──────────┐ ┌───────────────┐      │
          │  │Obs Engine │ │Mem Engine│ │Eval Engine    │      │
          │  └───────────┘ └──────────┘ └───────────────┘      │
          │  ┌───────────┐ ┌──────────┐ ┌───────────────┐      │
          │  │Exp Engine │ │Bench Eng │ │Prompt Optimizer│     │
          │  └───────────┘ └──────────┘ └───────────────┘      │
          │  ┌───────────┐ ┌───────────────────────┐           │
          │  │Tool Opt.  │ │Workflow Opt.          │           │
          │  └───────────┘ └───────────────────────┘           │
          └──────────────────┬───────────────────────────────┘
                             │
          ┌──────────────────▼───────────────────────────────┐
          │                   Agents                           │
          │  Planning | Reflection | Critic | Research        │
          │  Testing  | Deployment | Monitor| Logging         │
          │           Human Approval                            │
          └──────────────────┬───────────────────────────────┘
                             │
          ┌──────────────────▼───────────────────────────────┐
          │              Data Layer (SQLAlchemy)               │
          │  ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
          │  │SQLite/   │ │ChromaDB  │ │File Storage  │     │
          │  │PostgreSQL│ │(Vectors) │ │(Logs,Data)   │     │
          │  └──────────┘ └──────────┘ └──────────────┘     │
          └───────────────────────────────────────────────────┘
```

## Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `observations` | All system observations (interactions, errors, costs) |
| `tool_usages` | Per-tool invocation records linked to observations |
| `experiments` | Experiment proposals, branches, status, results |
| `evaluations` | Per-metric evaluation results per experiment |
| `benchmarks` | Standardized benchmark run results |
| `memory_entries` | Short-term, long-term, semantic, task memory |
| `agent_executions` | Agent execution traces with steps, errors |
| `deployments` | Deployment records with strategies, checkpoints |
| `leaderboard` | Ranked experiment performance leaderboard |
| `prompt_versions` | Versioned prompt templates with performance metrics |
| `workflow_versions` | Versioned workflow definitions |
| `tool_versions` | Versioned tool implementations |

## Safety Architecture

```
                    ┌──────────────────┐
                    │  Experiment      │
                    │  (Isolated Branch)│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Run All Tests   │
                    │  • Unit          │
                    │  • Integration   │
                    │  • Regression    │
                    │  • Security      │
                    │  • Stress        │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Evaluation      │
                    │  • Accuracy      │
                    │  • Cost          │
                    │  • Regression    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
              ┌─────┤ All Checks Pass? ├─────┐
              │ NO  └─────────────────┘ YES │
              │                              │
     ┌────────▼────────┐          ┌─────────▼───────┐
     │  Reject &       │          │ Human Approval  │
     │  Rollback       │          │ (optional)      │
     └─────────────────┘          └─────────┬───────┘
                                            │
                                   ┌────────▼───────┐
                                   │ Canary Deploy  │
                                   │ (10% traffic)  │
                                   └────────┬───────┘
                                            │
                                   ┌────────▼───────┐
                                   │ Monitor 24h    │
                                   └────────┬───────┘
                                            │
                                   ┌────────▼───────┐
                                   │ Full Deploy    │
                                   └────────────────┘
```

## Deployment Strategy Comparison

| Strategy | Risk | Speed | Rollback | Best For |
|----------|------|-------|----------|----------|
| Canary | Low | Slow | Easy | Critical systems |
| Blue-Green | Low | Fast | Easy | Stateless services |
| Rolling | Medium | Medium | Moderate | Containerized apps |
| Full | High | Instant | Hard | Non-critical updates |
