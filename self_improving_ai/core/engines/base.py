"""Base engine class providing shared functionality for all system engines."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from config.settings import settings

logger = structlog.get_logger(__name__)


@dataclass
class EngineMetrics:
    """Metrics tracked by every engine."""
    calls: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    @property
    def success_rate(self) -> float:
        total = self.calls
        if total == 0:
            return 1.0
        return (total - self.errors) / total

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.calls, 1)


class BaseEngine(ABC):
    """Base class for all system engines with standard lifecycle."""

    name: str = "base_engine"

    def __init__(self) -> None:
        self._metrics = EngineMetrics()
        self._started_at: datetime | None = None
        logger.info("engine.initialized", engine=self.name)

    def start(self) -> None:
        """Initialize engine resources."""
        self._started_at = datetime.utcnow()
        logger.info("engine.started", engine=self.name)

    def stop(self) -> None:
        """Clean up engine resources."""
        logger.info("engine.stopped", engine=self.name)

    def _record_call(self, latency_ms: float, success: bool = True) -> None:
        self._metrics.calls += 1
        self._metrics.total_latency_ms += latency_ms
        if not success:
            self._metrics.errors += 1

    def get_metrics(self) -> dict[str, Any]:
        return {
            "engine": self.name,
            "calls": self._metrics.calls,
            "errors": self._metrics.errors,
            "avg_latency_ms": self._metrics.avg_latency_ms,
            "success_rate": self._metrics.success_rate,
        }

    def health_check(self) -> bool:
        return self._metrics.success_rate >= 0.95


class AsyncEngine(BaseEngine):
    """Base class for engines that require async initialization."""

    async def async_start(self) -> None:
        self.start()

    async def async_stop(self) -> None:
        self.stop()
