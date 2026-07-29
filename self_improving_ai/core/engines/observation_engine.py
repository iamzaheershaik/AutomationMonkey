"""
Observation Engine

Collects:
- User interactions
- Tool usage
- Errors
- Latency
- Costs
- Token usage
- Failures
- Human feedback
- Success rate

Stores everything in structured memory via the database.
"""

from __future__ import annotations

import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

import structlog
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.engines.base import BaseEngine
from core.models import (
    FailureCategory,
    Observation,
    ObservationType,
    ToolUsage,
)

logger = structlog.get_logger(__name__)


class ObservationEngine(BaseEngine):
    """Collects and stores all system observations."""

    name = "observation_engine"

    def record_observation(
        self,
        observation_type: ObservationType,
        session_id: str = "",
        task_id: str = "",
        payload: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        cost_usd: float | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        success: bool | None = None,
        failure_category: FailureCategory | None = None,
        error_message: str = "",
        stack_trace: str = "",
        human_rating: int | None = None,
        human_comment: str = "",
        model_confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Observation:
        """Record a single observation into persistent storage."""
        start = time.monotonic()

        obs = Observation(
            observation_type=observation_type,
            session_id=session_id,
            task_id=task_id,
            payload=payload or {},
            extra_data=metadata or {},
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=success,
            failure_category=failure_category,
            error_message=error_message,
            stack_trace=stack_trace,
            human_rating=human_rating,
            human_comment=human_comment,
            model_confidence=model_confidence,
        )

        with SessionLocal() as db:
            db.add(obs)
            db.commit()
            db.expunge(obs)

        elapsed = (time.monotonic() - start) * 1000
        self._record_call(elapsed, success if success is not None else True)

        logger.debug(
            "observation.recorded",
            type=observation_type.value,
            session=session_id,
            success=success,
        )
        return obs

    def record_tool_usage(
        self,
        observation_id: str,
        tool_name: str,
        tool_version: str = "1.0.0",
        arguments: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        success: bool = True,
        latency_ms: float | None = None,
        cost_usd: float | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
    ) -> ToolUsage:
        """Record a tool invocation linked to an observation."""
        tool_usage = ToolUsage(
            observation_id=observation_id,
            tool_name=tool_name,
            tool_version=tool_version,
            arguments=arguments or {},
            result=result or {},
            success=success,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

        with SessionLocal() as db:
            db.add(tool_usage)
            db.commit()

        return tool_usage

    @contextmanager
    def observe_task(
        self,
        observation_type: ObservationType,
        session_id: str = "",
        task_id: str = "",
    ) -> Generator[dict[str, Any], None, None]:
        """Context manager that automatically records success/failure of a task.

        Usage:
            with obs_engine.observe_task(ObservationType.USER_INTERACTION, sid) as ctx:
                result = do_work()
                ctx["payload"] = {"result": result}
                ctx["success"] = True
        """
        ctx: dict[str, Any] = {
            "session_id": session_id,
            "task_id": task_id,
            "observation_type": observation_type,
            "success": True,
            "payload": {},
            "error_message": "",
            "stack_trace": "",
        }
        ctx_start = time.monotonic()

        try:
            yield ctx
        except Exception as exc:
            ctx["success"] = False
            ctx["error_message"] = str(exc)
            ctx["stack_trace"] = traceback.format_exc()
            logger.error("task.failed", error=str(exc), task_id=task_id)
            raise
        finally:
            ctx["latency_ms"] = (time.monotonic() - ctx_start) * 1000
            failure_cat = None if ctx["success"] else FailureCategory.UNKNOWN
            self.record_observation(
                observation_type=ctx["observation_type"],
                session_id=ctx["session_id"],
                task_id=ctx["task_id"],
                payload=ctx.get("payload", {}),
                latency_ms=ctx.get("latency_ms"),
                success=ctx["success"],
                failure_category=failure_cat,
                error_message=ctx.get("error_message", ""),
                stack_trace=ctx.get("stack_trace", ""),
                metadata=ctx.get("metadata"),
            )

    def get_session_observations(
        self, session_id: str, limit: int = 100
    ) -> list[Observation]:
        """Retrieve all observations for a given session."""
        with SessionLocal() as db:
            return (
                db.query(Observation)
                .filter(Observation.session_id == session_id)
                .order_by(Observation.timestamp.desc())
                .limit(limit)
                .all()
            )

    def get_failure_rate(
        self, window_hours: int = 24
    ) -> dict[str, Any]:
        """Calculate failure rates over a rolling window."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        # Simple query against DB
        with SessionLocal() as db:
            total = db.query(Observation).filter(
                Observation.timestamp >= cutoff
            ).count()

            failures = db.query(Observation).filter(
                Observation.timestamp >= cutoff,
                Observation.success == False,  # noqa: E712
            ).count()

        return {
            "total_observations": total,
            "failures": failures,
            "failure_rate": failures / max(total, 1),
            "window_hours": window_hours,
        }

    def get_category_breakdown(
        self, window_hours: int = 24
    ) -> dict[str, int]:
        """Break failures down by category."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        with SessionLocal() as db:
            rows = (
                db.query(
                    Observation.failure_category,
                    db.func.count(Observation.id),
                )
                .filter(
                    Observation.timestamp >= cutoff,
                    Observation.success == False,  # noqa: E712
                )
                .group_by(Observation.failure_category)
                .all()
            )
        return {cat.value if cat else "unknown": cnt for cat, cnt in rows}
