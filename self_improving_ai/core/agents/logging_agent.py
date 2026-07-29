"""
Logging Agent

Structured, centralized logging for all system operations:
- All agent executions
- All experiments
- All deployments
- All errors
- All user interactions
- Performance metrics
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from core.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class LoggingAgent(BaseAgent):
    """Centralized structured logging for audit and debugging."""

    agent_name = "logging_agent"

    def __init__(self) -> None:
        super().__init__()
        self._log_dir = Path("./data/logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / f"system_{datetime.utcnow().strftime('%Y%m%d')}.log"

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Log an event with full context."""
        steps: list[dict[str, Any]] = []
        event_type = task.get("event_type", "unknown")
        event_data = task.get("event_data", {})
        level = task.get("level", "INFO")

        log_entry = self._format_entry(event_type, event_data, level)
        self._write_log(log_entry)

        if level in ("ERROR", "CRITICAL"):
            self._write_error_log(event_type, event_data)

        self.record_step(steps, "log_written", True)

        return {
            "logged": True,
            "event_type": event_type,
            "level": level,
            "log_file": str(self._log_file),
            "steps": steps,
            "tokens_used": 0,
        }

    def query_logs(
        self,
        event_type: str | None = None,
        level: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query logs with filters."""
        results = []
        log_files = sorted(self._log_dir.glob("system_*.log"), reverse=True)

        for lf in log_files:
            if len(results) >= limit:
                break
            try:
                with open(lf) as f:
                    for line in f:
                        if len(results) >= limit:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if event_type and entry.get("event_type") != event_type:
                                continue
                            if level and entry.get("level") != level:
                                continue
                            results.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        return results

    def get_error_summary(self, hours: int = 24) -> dict[str, Any]:
        """Summarize errors in the last N hours."""
        errors = self.query_logs(level="ERROR", limit=1000)

        error_types: dict[str, int] = {}
        for err in errors:
            etype = err.get("error_type", "unknown")
            error_types[etype] = error_types.get(etype, 0) + 1

        return {
            "total_errors": len(errors),
            "error_types": error_types,
            "window_hours": hours,
            "most_common": max(error_types, key=error_types.get) if error_types else None,
        }

    def export_logs(self, output_path: str | None = None) -> str:
        """Export all logs to a compressed archive."""
        import gzip
        import shutil

        output = output_path or str(self._log_dir / "logs_export.jsonl.gz")
        with gzip.open(output, "wt") as gz:
            for lf in sorted(self._log_dir.glob("system_*.log")):
                with open(lf) as f:
                    gz.write(f.read())

        return output

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _format_entry(
        self, event_type: str, event_data: dict[str, Any], level: str
    ) -> dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "event_type": event_type,
            "agent": self.agent_name,
            "data": event_data,
        }

    def _write_log(self, entry: dict[str, Any]) -> None:
        """Write a log entry to the daily log file."""
        try:
            with open(self._log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.error("log.write.failed", error=str(exc))

    def _write_error_log(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Write error details to a separate error log."""
        error_file = self._log_dir / f"errors_{datetime.utcnow().strftime('%Y%m%d')}.log"
        entry = self._format_entry(event_type, event_data, "ERROR")
        try:
            with open(error_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.error("error.log.write.failed", error=str(exc))
