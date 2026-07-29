"""
Critic Agent

Evaluates outputs, plans, and proposals with critical scrutiny:
- Validates correctness
- Identifies flaws
- Suggests improvements
- Scores quality
- Detects hallucinations
"""

from __future__ import annotations

from typing import Any

import structlog

from core.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class CriticAgent(BaseAgent):
    """Critically evaluates outputs and identifies issues."""

    agent_name = "critic_agent"

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Critique the given content with detailed feedback."""
        steps: list[dict[str, Any]] = []
        content = task.get("content", {})
        criteria = task.get("criteria", [])

        self.record_step(steps, "validate_correctness", True)
        correctness = self._check_correctness(content)

        self.record_step(steps, "check_hallucinations", True)
        hallucinations = self._detect_hallucinations(content)

        self.record_step(steps, "assess_quality", True)
        quality = self._assess_quality(content, criteria)

        self.record_step(steps, "generate_feedback", True)
        feedback = self._generate_feedback(correctness, hallucinations, quality)

        overall_score = self._compute_overall_score(correctness, quality, hallucinations)

        critique = {
            "overall_score": overall_score,
            "correctness": correctness,
            "hallucinations": hallucinations,
            "quality": quality,
            "feedback": feedback,
            "verdict": "ACCEPT" if overall_score >= 0.7 else "REVISE",
        }

        logger.info(
            "critic.completed",
            score=overall_score,
            verdict=critique["verdict"],
        )
        return {"critique": critique, "steps": steps, "tokens_used": 0}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_correctness(self, content: dict[str, Any]) -> dict[str, Any]:
        """Validate factual correctness and logical consistency."""
        issues = []
        score = 1.0

        output = content.get("output", "")
        expected = content.get("expected", "")

        if expected and output:
            if expected != output:
                issues.append({
                    "type": "mismatch",
                    "severity": "high",
                    "detail": "Output does not match expected result",
                })
                score -= 0.3

        if isinstance(output, str) and len(output) > 0:
            # Check for empty/vague outputs
            vague_phrases = ["I don't know", "I'm not sure", "maybe", "perhaps", "could be"]
            for phrase in vague_phrases:
                if phrase.lower() in output.lower():
                    issues.append({
                        "type": "uncertainty",
                        "severity": "low",
                        "detail": f"Output contains uncertain language: '{phrase}'",
                    })
                    score -= 0.05

        return {"score": max(score, 0.0), "issues": issues}

    def _detect_hallucinations(self, content: dict[str, Any]) -> dict[str, Any]:
        """Detect potential hallucination patterns."""
        flags = []
        output = str(content.get("output", ""))
        source_data = str(content.get("source_data", ""))

        # Heuristic: output references things not in source data
        if source_data and output:
            output_lower = output.lower()
            source_lower = source_data.lower()

            # Extract numbers from output and check if they appear in source
            import re
            numbers_in_output = re.findall(r"\b\d{4,}\b", output)
            for num in numbers_in_output[:10]:
                if num not in source_data:
                    flags.append({
                        "type": "unreferenced_number",
                        "detail": f"Number '{num}' not found in source data",
                    })

            # Check for fabricated names/entities
            capitalized_words = re.findall(r"\b[A-Z][a-z]{2,}\b", output)
            for word in capitalized_words[:10]:
                if word.lower() not in source_lower and word.lower() not in output_lower.replace(word.lower(), ""):
                    flags.append({
                        "type": "potential_fabrication",
                        "detail": f"Entity '{word}' may be fabricated",
                    })

        score = max(1.0 - len(flags) * 0.1, 0.0)
        return {"score": score, "flags": flags}

    def _assess_quality(
        self, content: dict[str, Any], criteria: list[str]
    ) -> dict[str, Any]:
        """Assess overall quality against criteria."""
        output = str(content.get("output", ""))
        scores = {}

        if "clarity" in criteria or not criteria:
            scores["clarity"] = min(1.0, max(0.3, len(output.split()) / 50))
        if "conciseness" in criteria or not criteria:
            word_count = len(output.split())
            scores["conciseness"] = 1.0 if word_count < 200 else 0.5
        if "completeness" in criteria or not criteria:
            scores["completeness"] = 0.8 if len(output) > 50 else 0.3

        overall = sum(scores.values()) / max(len(scores), 1)
        return {"score": overall, "dimension_scores": scores}

    def _generate_feedback(
        self,
        correctness: dict[str, Any],
        hallucinations: dict[str, Any],
        quality: dict[str, Any],
    ) -> list[str]:
        """Generate actionable feedback from critique."""
        feedback = []

        for issue in correctness.get("issues", []):
            feedback.append(f"[{issue['severity'].upper()}] {issue['detail']}")

        for flag in hallucinations.get("flags", []):
            feedback.append(f"[HALLUCINATION] {flag['detail']}")

        if quality["score"] < 0.6:
            feedback.append("[QUALITY] Overall quality needs improvement")
            for dim, score in quality.get("dimension_scores", {}).items():
                if score < 0.6:
                    feedback.append(f"  - {dim}: {score:.2f}")

        return feedback

    @staticmethod
    def _compute_overall_score(
        correctness: dict[str, Any],
        quality: dict[str, Any],
        hallucinations: dict[str, Any],
    ) -> float:
        """Weighted composite score."""
        return (
            correctness.get("score", 0) * 0.4
            + quality.get("score", 0) * 0.3
            + hallucinations.get("score", 0) * 0.3
        )
