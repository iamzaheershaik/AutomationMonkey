"""
Human Approval Agent

Manages the human-in-the-loop approval workflow:
- Request approval for experiments
- Track approval status
- Enforce approval policies
- Maintain approval audit trail

Safety requirement: critical changes require human sign-off.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from core.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class HumanApprovalAgent(BaseAgent):
    """Manages human approval for experiments and deployments."""

    agent_name = "human_approval_agent"

    def __init__(self) -> None:
        super().__init__()
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._approval_history: list[dict[str, Any]] = []
        self._policies: dict[str, dict[str, Any]] = {
            "default": {
                "require_approval": True,
                "auto_approve": False,
            },
            "minor_improvement": {
                "require_approval": True,
                "auto_approve": False,
                "description": "Improvements <5% change require one reviewer",
            },
            "major_improvement": {
                "require_approval": True,
                "auto_approve": False,
                "description": "Improvements >=5% change require two reviewers",
            },
            "security_change": {
                "require_approval": True,
                "auto_approve": False,
                "description": "Security changes require security lead approval",
            },
            "emergency_fix": {
                "require_approval": False,
                "auto_approve": True,
                "description": "Emergency fixes may bypass approval with post-hoc review",
            },
        }

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Handle an approval workflow action."""
        steps: list[dict[str, Any]] = []
        action = task.get("action", "request")

        if action == "request":
            self.record_step(steps, "create_approval_request", True)
            result = self.request_approval(
                experiment_id=task.get("experiment_id", ""),
                experiment_name=task.get("experiment_name", ""),
                details=task.get("details", {}),
                risk_level=task.get("risk_level", "minor"),
                auto_approve_threshold=task.get("auto_approve_threshold", 0.0),
            )

        elif action == "approve":
            self.record_step(steps, "process_approval", True)
            result = self.approve(
                approval_id=task.get("approval_id", ""),
                reviewer=task.get("reviewer", "system"),
                comment=task.get("comment", ""),
            )

        elif action == "reject":
            self.record_step(steps, "process_rejection", True)
            result = self.reject(
                approval_id=task.get("approval_id", ""),
                reviewer=task.get("reviewer", "system"),
                reason=task.get("reason", ""),
            )

        elif action == "check":
            self.record_step(steps, "check_status", True)
            result = self.check_status(task.get("experiment_id", ""))

        else:
            result = {"error": f"Unknown action: {action}"}

        return {**result, "steps": steps, "tokens_used": 0}

    def request_approval(
        self,
        experiment_id: str,
        experiment_name: str,
        details: dict[str, Any],
        risk_level: str = "minor",
        auto_approve_threshold: float = 0.0,
    ) -> dict[str, Any]:
        """Request human approval for an experiment or change.

        Returns the approval request with status.
        """
        import uuid

        # Check auto-approve policy
        if auto_approve_threshold > 0 and risk_level == "minor":
            improvement = details.get("actual_improvement", 0) or details.get("expected_improvement", 0)
            if 0 < improvement < auto_approve_threshold:
                return self._auto_approve(experiment_id, experiment_name, details, risk_level)

        approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        request = {
            "approval_id": approval_id,
            "experiment_id": experiment_id,
            "experiment_name": experiment_name,
            "details": details,
            "risk_level": risk_level,
            "status": "pending",
            "requested_at": datetime.utcnow().isoformat(),
            "required_reviewers": 2 if risk_level == "major" else 1,
            "reviewers": [],
        }

        self._pending_approvals[approval_id] = request

        policy = self._get_policy(risk_level)
        request["policy"] = policy

        logger.info(
            "approval.requested",
            approval_id=approval_id,
            experiment=experiment_name,
            risk_level=risk_level,
        )

        return request

    def approve(
        self,
        approval_id: str,
        reviewer: str = "system",
        comment: str = "",
    ) -> dict[str, Any]:
        """Approve a pending request."""
        request = self._pending_approvals.get(approval_id)
        if not request:
            return {"error": f"Approval {approval_id} not found"}

        request.setdefault("reviewers", [])
        request["reviewers"].append({
            "reviewer": reviewer,
            "timestamp": datetime.utcnow().isoformat(),
            "comment": comment,
        })

        required = request.get("required_reviewers", 1)
        if len(request["reviewers"]) >= required:
            request["status"] = "approved"
            request["approved_at"] = datetime.utcnow().isoformat()
            logger.info("approval.granted", approval_id=approval_id, reviewer=reviewer)

        self._approval_history.append(dict(request))
        return dict(request)

    def reject(
        self,
        approval_id: str,
        reviewer: str = "system",
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a pending request."""
        request = self._pending_approvals.get(approval_id)
        if not request:
            return {"error": f"Approval {approval_id} not found"}

        request["status"] = "rejected"
        request["rejected_at"] = datetime.utcnow().isoformat()
        request["rejected_by"] = reviewer
        request["rejection_reason"] = reason

        self._approval_history.append(dict(request))
        logger.info("approval.rejected", approval_id=approval_id, reviewer=reviewer, reason=reason)

        return dict(request)

    def check_status(self, experiment_id: str) -> dict[str, Any]:
        """Check approval status for an experiment."""
        for req in self._pending_approvals.values():
            if req.get("experiment_id") == experiment_id:
                return {"experiment_id": experiment_id, "status": req["status"], "approval": req}

        # Check history
        for req in reversed(self._approval_history):
            if req.get("experiment_id") == experiment_id:
                return {"experiment_id": experiment_id, "status": req["status"], "approval": req}

        return {"experiment_id": experiment_id, "status": "not_requested"}

    def get_pending(self) -> list[dict[str, Any]]:
        """Get all pending approval requests."""
        return [r for r in self._pending_approvals.values() if r["status"] == "pending"]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get approval history."""
        return self._approval_history[-limit:]

    def set_policy(self, name: str, policy: dict[str, Any]) -> None:
        """Add or update an approval policy."""
        self._policies[name] = policy

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _auto_approve(
        self,
        experiment_id: str,
        experiment_name: str,
        details: dict[str, Any],
        risk_level: str,
    ) -> dict[str, Any]:
        """Auto-approve a low-risk change."""
        import uuid
        approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        request = {
            "approval_id": approval_id,
            "experiment_id": experiment_id,
            "experiment_name": experiment_name,
            "details": details,
            "risk_level": risk_level,
            "status": "approved",
            "auto_approved": True,
            "approved_at": datetime.utcnow().isoformat(),
            "reviewers": [{"reviewer": "system", "comment": "Auto-approved below threshold"}],
        }

        self._pending_approvals[approval_id] = request
        self._approval_history.append(dict(request))
        logger.info("approval.auto_approved", approval_id=approval_id, experiment=experiment_name)
        return dict(request)

    def _get_policy(self, risk_level: str) -> dict[str, Any]:
        """Get the applicable policy for a risk level."""
        return self._policies.get(risk_level, self._policies["default"])
