"""
Prompt Optimizer Engine

Generates and tests improved prompt templates.
- Analyzes failure patterns
- Generates multiple prompt variant proposals
- Evaluates each via controlled experiments
- Selects the best variant based on measurable metrics
"""

from __future__ import annotations

import copy
import re
from datetime import datetime
from typing import Any

import structlog

from core.engines.base import BaseEngine
from core.models import ImprovementType, PromptVersion

logger = structlog.get_logger(__name__)


class PromptOptimizer(BaseEngine):
    """Optimizes prompt templates using iterative experimentation."""

    name = "prompt_optimizer"

    def analyze_prompt(
        self,
        prompt: PromptVersion,
        failure_cases: list[dict[str, Any]],
        success_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze a prompt's performance to identify weaknesses.

        Returns a diagnostic report with specific improvement recommendations.
        """
        issues: list[dict[str, Any]] = []
        total = len(failure_cases) + len(success_cases)
        failure_rate = len(failure_cases) / max(total, 1)

        analysis = {
            "prompt_name": prompt.name,
            "prompt_version": prompt.version,
            "total_samples": total,
            "failure_rate": failure_rate,
            "success_rate": 1 - failure_rate,
            "issues": issues,
        }

        # Categorize failures
        categories: dict[str, int] = {}
        for fc in failure_cases:
            cat = fc.get("failure_category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        analysis["failure_categories"] = categories

        # Generate improvement suggestions based on patterns
        suggestions = self._generate_suggestions(failure_cases, success_cases, prompt)
        analysis["suggestions"] = suggestions

        return analysis

    def generate_variants(
        self,
        base_prompt: PromptVersion,
        analysis: dict[str, Any],
        num_variants: int = 5,
    ) -> list[PromptVersion]:
        """Generate multiple prompt variants based on analysis.

        Variant strategies:
        1. Add explicit instructions for common failure modes
        2. Add few-shot examples from success cases
        3. Restructure for clarity (chain-of-thought, step-by-step)
        4. Add constraints/guardrails for known hallucination patterns
        5. Optimize for token efficiency
        """
        variants: list[PromptVersion] = []

        strategies = [
            ("explicit_instructions", self._variant_add_instructions),
            ("few_shot_examples", self._variant_add_examples),
            ("chain_of_thought", self._variant_chain_of_thought),
            ("constraints", self._variant_add_constraints),
            ("concise", self._variant_concise),
        ]

        for i, (strat_name, strat_fn) in enumerate(strategies[:num_variants]):
            try:
                variant_template = strat_fn(base_prompt, analysis)
                variant = PromptVersion(
                    name=base_prompt.name,
                    version=f"{base_prompt.version}.opt{i+1}",
                    template=variant_template,
                    variables=copy.deepcopy(base_prompt.variables),
                    model=base_prompt.model,
                    is_active=False,
                )
                variants.append(variant)
            except Exception as exc:
                logger.warning(
                    "variant.generation.failed",
                    strategy=strat_name,
                    error=str(exc),
                )

        logger.info("prompt.variants.generated", count=len(variants), prompt=base_prompt.name)
        return variants

    def evaluate_variant(
        self,
        original: PromptVersion,
        variant: PromptVersion,
        test_cases: list[dict[str, Any]],
        evaluator_fn,
    ) -> dict[str, Any]:
        """Evaluate a prompt variant against the original on test cases."""
        results = {"variant_id": variant.id, "original_score": 0.0, "variant_score": 0.0, "results": []}

        for tc in test_cases:
            orig_result = evaluator_fn(original, tc)
            var_result = evaluator_fn(variant, tc)
            results["results"].append({
                "input": tc.get("input", ""),
                "original": orig_result,
                "variant": var_result,
                "improved": var_result.get("score", 0) > orig_result.get("score", 0),
            })

        scores_orig = [r["original"].get("score", 0) for r in results["results"]]
        scores_var = [r["variant"].get("score", 0) for r in results["results"]]

        results["original_score"] = sum(scores_orig) / max(len(scores_orig), 1)
        results["variant_score"] = sum(scores_var) / max(len(scores_var), 1)
        results["improvement"] = results["variant_score"] - results["original_score"]
        results["improved_cases"] = sum(1 for r in results["results"] if r["improved"])

        return results

    # ------------------------------------------------------------------
    # Variant generators
    # ------------------------------------------------------------------

    @staticmethod
    def _variant_add_instructions(
        prompt: PromptVersion, analysis: dict[str, Any]
    ) -> str:
        """Add explicit instructions targeting common failure modes."""
        failure_cats = analysis.get("failure_categories", {})
        top_failure = max(failure_cats, key=failure_cats.get) if failure_cats else "accuracy"

        instructions = f"\n\n## Critical Instructions\n"
        instructions += f"- Pay special attention to avoiding {top_failure.replace('_', ' ')} errors.\n"
        instructions += "- Double-check your output before responding.\n"
        instructions += "- If uncertain, acknowledge the uncertainty rather than guessing.\n"

        return prompt.template.rstrip() + instructions

    @staticmethod
    def _variant_add_examples(
        prompt: PromptVersion, analysis: dict[str, Any]
    ) -> str:
        """Add few-shot examples based on a heuristic template."""
        few_shot = "\n\n## Examples\n"
        few_shot += "Example 1:\nInput: [example input]\nOutput: [expected output]\n\n"
        few_shot += "Example 2:\nInput: [example input]\nOutput: [expected output]\n"
        return prompt.template.rstrip() + few_shot

    @staticmethod
    def _variant_chain_of_thought(
        prompt: PromptVersion, analysis: dict[str, Any]
    ) -> str:
        """Restructure prompt to encourage chain-of-thought reasoning."""
        cot_prefix = "Think step by step:\n1. First, understand the problem.\n2. Identify key information.\n"
        cot_prefix += "3. Reason through the solution.\n4. Provide your final answer.\n\n"
        return cot_prefix + prompt.template

    @staticmethod
    def _variant_add_constraints(
        prompt: PromptVersion, analysis: dict[str, Any]
    ) -> str:
        """Add explicit constraints and guardrails."""
        constraints = "\n\n## Constraints\n"
        constraints += "- Only use information provided in the input.\n"
        constraints += "- Do not fabricate, hallucinate, or assume missing data.\n"
        constraints += "- If information is insufficient, respond with 'INSUFFICIENT_DATA'.\n"
        return prompt.template.rstrip() + constraints

    @staticmethod
    def _variant_concise(
        prompt: PromptVersion, analysis: dict[str, Any]
    ) -> str:
        """Optimize prompt for brevity and token efficiency."""
        concise = re.sub(r"\s+", " ", prompt.template).strip()
        return concise

    @staticmethod
    def _generate_suggestions(
        failure_cases: list[dict[str, Any]],
        success_cases: list[dict[str, Any]],
        prompt: PromptVersion,
    ) -> list[dict[str, Any]]:
        """Generate actionable improvement suggestions from failure patterns."""
        suggestions = []
        failure_cats: dict[str, int] = {}
        for fc in failure_cases:
            cat = fc.get("failure_category", "unknown")
            failure_cats[cat] = failure_cats.get(cat, 0) + 1

        if failure_cats.get("hallucination", 0) > 0:
            suggestions.append({
                "type": "add_constraints",
                "reason": f"{failure_cats['hallucination']} hallucination failures detected",
                "action": "Add explicit anti-hallucination guardrails to the prompt",
            })

        if failure_cats.get("incorrect_output", 0) > 0:
            suggestions.append({
                "type": "add_examples",
                "reason": f"{failure_cats['incorrect_output']} incorrect output failures",
                "action": "Include verified few-shot examples from success cases",
            })

        if failure_cats.get("parse_error", 0) > 0:
            suggestions.append({
                "type": "format_specification",
                "reason": f"{failure_cats['parse_error']} parse error failures",
                "action": "Specify exact output format in the prompt",
            })

        if prompt.avg_latency_ms is not None and prompt.avg_latency_ms > 5000:
            suggestions.append({
                "type": "shorten_prompt",
                "reason": f"High average latency ({prompt.avg_latency_ms:.0f}ms)",
                "action": "Shorten prompt and remove redundant instructions",
            })

        return suggestions
