"""
Monitoring Agent

Continuous system health monitoring:
- Failures
- User feedback
- Performance
- Costs
- Errors
- Alerting
"""

from __future__ import annotations

from typing import Any

import structlog

from core.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class MonitoringAgent(BaseAgent):
    """Monitors system health and triggers alerts."""

    agent_name = "monitoring_agent"

    def __init__(self) -> None:
        super().__init__()
        self._thresholds: dict[str, float] = {
            "failure_rate": 0.05,       # Alert if >5% failure rate
            "latency_p95_ms": 5000,     # Alert if p95 > 5s
            "cost_per_hour_usd": 1.00,  # Alert if >$1/hr
            "error_rate": 0.02,         # Alert if >2% errors
            "user_satisfaction": 3.5,   # Alert if below 3.5/5
        }
        self._alerts: list[dict[str, Any]] = []
        self._alert_handlers: list[callable] = []

    def set_threshold(self, metric: str, value: float) -> None:
        """Update a monitoring threshold."""
        self._thresholds[metric] = value

    def add_alert_handler(self, handler: callable) -> None:
        """Register a custom alert handler."""
        self._alert_handlers.append(handler)

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Run a monitoring check cycle."""
        steps: list[dict[str, Any]] = []
        metrics = task.get("metrics", {})
        active_alerts: list[dict[str, Any]] = []

        self.record_step(steps, "check_failures", True)
        if self._check_failure_rate(metrics):
            active_alerts.append({
                "type": "failure_rate",
                "severity": "critical",
                "value": metrics.get("failure_rate", 0),
                "threshold": self._thresholds["failure_rate"],
            })

        self.record_step(steps, "check_latency", True)
        if self._check_latency(metrics):
            active_alerts.append({
                "type": "latency",
                "severity": "warning",
                "value": metrics.get("latency_p95_ms", 0),
                "threshold": self._thresholds["latency_p95_ms"],
            })

        self.record_step(steps, "check_costs", True)
        if self._check_cost(metrics):
            active_alerts.append({
                "type": "cost",
                "severity": "warning",
                "value": metrics.get("cost_per_hour_usd", 0),
                "threshold": self._thresholds["cost_per_hour_usd"],
            })

        self.record_step(steps, "check_errors", True)
        if self._check_error_rate(metrics):
            active_alerts.append({
                "type": "error_rate",
                "severity": "critical",
                "value": metrics.get("error_rate", 0),
                "threshold": self._thresholds["error_rate"],
            })

        self.record_step(steps, "check_satisfaction", True)
        if self._check_satisfaction(metrics):
            active_alerts.append({
                "type": "user_satisfaction",
                "severity": "warning",
                "value": metrics.get("user_satisfaction", 0),
                "threshold": self._thresholds["user_satisfaction"],
            })

        # Dispatch alerts
        for alert in active_alerts:
            self._dispatch_alert(alert)

        status = "healthy" if len(active_alerts) == 0 else "degraded"
        if any(a["severity"] == "critical" for a in active_alerts):
            status = "critical"

        self._alerts = active_alerts

        logger.info(
            "monitoring.cycle.completed",
            status=status,
            alerts=len(active_alerts),
        )

        return {
            "status": status,
            "alerts": active_alerts,
            "metrics_checked": list(metrics.keys()),
            "thresholds": self._thresholds,
            "steps": steps,
            "tokens_used": 0,
        }

    def get_alerts(self) -> list[dict[str, Any]]:
        """Retrieve current active alerts."""
        return self._alerts

    def get_dashboard(self) -> dict[str, Any]:
        """Generate a monitoring dashboard summary."""
        return {
            "agent": self.agent_name,
            "status": "critical" if any(
                a["severity"] == "critical" for a in self._alerts
            ) else "healthy",
            "active_alerts": len(self._alerts),
            "alerts": self._alerts,
            "thresholds": self._thresholds,
        }

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_failure_rate(self, metrics: dict[str, Any]) -> bool:
        return metrics.get("failure_rate", 0) > self._thresholds["failure_rate"]

    def _check_latency(self, metrics: dict[str, Any]) -> bool:
        return metrics.get("latency_p95_ms", 0) > self._thresholds["latency_p95_ms"]

    def _check_cost(self, metrics: dict[str, Any]) -> bool:
        return metrics.get("cost_per_hour_usd", 0) > self._thresholds["cost_per_hour_usd"]

    def _check_error_rate(self, metrics: dict[str, Any]) -> bool:
        return metrics.get("error_rate", 0) > self._thresholds["error_rate"]

    def _check_satisfaction(self, metrics: dict[str, Any]) -> bool:
        return metrics.get("user_satisfaction", 5.0) < self._thresholds["user_satisfaction"]

    def _dispatch_alert(self, alert: dict[str, Any]) -> None:
        """Dispatch alert to all registered handlers."""
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as exc:
                logger.error("alert.handler.failed", error=str(exc))

        logger.warning(
            "alert.triggered",
            type=alert["type"],
            severity=alert["severity"],
            value=alert.get("value"),
        )
