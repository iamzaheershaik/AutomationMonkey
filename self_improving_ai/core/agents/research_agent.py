"""
Research Agent

Conducts research tasks:
- Information gathering
- Literature/web search
- Knowledge synthesis
- Summarization
- Fact extraction
"""

from __future__ import annotations

from typing import Any

import structlog

from core.agents.base import BaseAgent

logger = structlog.get_logger(__name__)


class ResearchAgent(BaseAgent):
    """Gathers, synthesizes, and structures information."""

    agent_name = "research_agent"

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Research the given query or topic."""
        steps: list[dict[str, Any]] = []
        query = task.get("query", "")
        sources = task.get("sources", [])
        depth = task.get("depth", "standard")

        self.record_step(steps, "gather_information", True)
        info = self._gather(query, sources)

        self.record_step(steps, "synthesize", True)
        synthesis = self._synthesize(info)

        self.record_step(steps, "extract_facts", True)
        facts = self._extract_facts(synthesis)

        self.record_step(steps, "generate_citations", True)
        citations = self._generate_citations(sources)

        result = {
            "query": query,
            "synthesis": synthesis,
            "key_facts": facts,
            "citations": citations,
            "depth": depth,
            "source_count": len(sources),
        }

        logger.info("research.completed", query=query[:80], facts=len(facts))
        return {"result": result, "steps": steps, "tokens_used": 0}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _gather(
        self, query: str, sources: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Gather information from sources."""
        results = {
            "query": query,
            "sources_used": len(sources),
            "collected_data": sources,
        }
        return results

    def _synthesize(self, info: dict[str, Any]) -> str:
        """Synthesize gathered information into coherent summary."""
        sources = info.get("collected_data", [])
        if not sources:
            return "No sources available for synthesis."

        key_points = []
        for src in sources:
            if isinstance(src, dict):
                content = src.get("content", src.get("text", str(src)))
                if len(content) > 10:
                    key_points.append(content[:200])

        return "\n\n".join(key_points[:5]) if key_points else "No content extracted from sources."

    def _extract_facts(self, synthesis: str) -> list[dict[str, Any]]:
        """Extract key factual claims from synthesis."""
        import re
        sentences = re.split(r"(?<=[.!?])\s+", synthesis)
        facts = []
        for i, sent in enumerate(sentences[:10]):
            if len(sent) > 20:
                facts.append({
                    "id": i + 1,
                    "claim": sent.strip(),
                    "confidence": 0.7,  # Placeholder
                })
        return facts

    def _generate_citations(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate structured citations from sources."""
        citations = []
        for i, src in enumerate(sources):
            citations.append({
                "id": i + 1,
                "source": src.get("source", src.get("title", f"Source {i+1}")),
                "url": src.get("url", ""),
                "access_date": src.get("access_date", ""),
            })
        return citations
