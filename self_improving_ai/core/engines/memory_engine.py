"""
Memory Engine

Manages multiple memory types:
- Short-term memory (recent interactions, sliding window)
- Long-term memory (persistent, importance-weighted)
- Semantic memory (vector embeddings, similarity search)
- Task memory (work-in-progress task state)
- Experiment history
- Benchmark history
- Prompt/workflow/code versions

Never loses historical data.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.orm import Session

from config.settings import settings
from core.database import SessionLocal
from core.engines.base import BaseEngine
from core.models import (
    Benchmark,
    Evaluation,
    Experiment,
    MemoryEntry,
    PromptVersion,
    ToolVersion,
    WorkflowVersion,
)

logger = structlog.get_logger(__name__)


class MemoryEngine(BaseEngine):
    """Unified memory management across short/long/semantic/task storage."""

    name = "memory_engine"

    def __init__(self) -> None:
        super().__init__()
        self._vector_store = None  # Lazy-init ChromaDB

    def store_short_term(
        self,
        key: str,
        value: dict[str, Any],
        session_id: str = "",
    ) -> MemoryEntry:
        """Store a short-term memory entry. Older entries are pruned."""
        return self._store_entry(
            memory_type="short_term",
            key=f"st:{session_id}:{key}",
            value=value,
            ttl_hours=1,
        )

    def store_long_term(
        self,
        key: str,
        value: dict[str, Any],
        importance: float = 0.5,
    ) -> MemoryEntry:
        """Store a long-term memory entry with importance weighting."""
        return self._store_entry(
            memory_type="long_term",
            key=f"lt:{key}",
            value=value,
            importance=importance,
        )

    def store_semantic(
        self,
        key: str,
        value: dict[str, Any],
        text_for_embedding: str = "",
    ) -> MemoryEntry:
        """Store semantic memory with vector embedding."""
        embedding_id = None
        if text_for_embedding:
            embedding_id = self._create_embedding(key, text_for_embedding, value)

        return self._store_entry(
            memory_type="semantic",
            key=f"sem:{key}",
            value=value,
            embedding_id=embedding_id,
        )

    def store_task(
        self,
        task_id: str,
        value: dict[str, Any],
    ) -> MemoryEntry:
        """Store task-specific memory."""
        return self._store_entry(
            memory_type="task",
            key=f"task:{task_id}",
            value=value,
        )

    def recall(
        self,
        key: str,
        memory_type: str | None = None,
    ) -> list[MemoryEntry]:
        """Recall memory entries by key."""
        with SessionLocal() as db:
            q = db.query(MemoryEntry)
            if memory_type:
                q = q.filter(MemoryEntry.memory_type == memory_type)
            entries = q.filter(MemoryEntry.key == key).all()

            for entry in entries:
                entry.access_count += 1
                entry.last_accessed = datetime.utcnow()
            db.commit()

            return entries

    def search_semantic(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search semantic memory via vector similarity."""
        if self._vector_store is None:
            return []
        try:
            results = self._vector_store.query(query_texts=[query], n_results=top_k)
            return [
                {"id": rid, "metadata": meta, "distance": dist}
                for rid, meta, dist in zip(
                    results.get("ids", [[]])[0],
                    results.get("metadatas", [[]])[0],
                    results.get("distances", [[]])[0],
                )
            ]
        except Exception as exc:
            logger.error("semantic_search.failed", error=str(exc))
            return []

    def recall_context(
        self,
        session_id: str = "",
        task_id: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Recall relevant context for a session or task."""
        result: dict[str, Any] = {
            "short_term": [],
            "long_term": [],
            "task": [],
        }

        with SessionLocal() as db:
            if session_id:
                st_entries = (
                    db.query(MemoryEntry)
                    .filter(
                        MemoryEntry.memory_type == "short_term",
                        MemoryEntry.key.like(f"st:{session_id}:%"),
                    )
                    .order_by(MemoryEntry.created_at.desc())
                    .limit(limit)
                    .all()
                )
                result["short_term"] = [e.value for e in st_entries]

            if task_id:
                task_entries = (
                    db.query(MemoryEntry)
                    .filter(
                        MemoryEntry.memory_type == "task",
                        MemoryEntry.key.like(f"%{task_id}%"),
                    )
                    .order_by(MemoryEntry.created_at.desc())
                    .limit(limit)
                    .all()
                )
                result["task"] = [e.value for e in task_entries]

            return result

    def prune_short_term(self) -> int:
        """Remove expired short-term memory entries."""
        cutoff = datetime.utcnow() - timedelta(hours=1)
        with SessionLocal() as db:
            deleted = (
                db.query(MemoryEntry)
                .filter(
                    MemoryEntry.memory_type == "short_term",
                    MemoryEntry.created_at < cutoff,
                )
                .delete()
            )
            db.commit()
        logger.debug("memory.pruned", type="short_term", count=deleted)
        return deleted

    # ------------------------------------------------------------------
    # Versioned artifact management
    # ------------------------------------------------------------------

    def store_prompt_version(self, prompt: PromptVersion) -> PromptVersion:
        with SessionLocal() as db:
            db.add(prompt)
            db.commit()
            db.refresh(prompt)
        return prompt

    def get_active_prompt(self, name: str) -> PromptVersion | None:
        with SessionLocal() as db:
            return (
                db.query(PromptVersion)
                .filter(PromptVersion.name == name, PromptVersion.is_active == True)  # noqa: E712
                .first()
            )

    def store_workflow_version(self, workflow: WorkflowVersion) -> WorkflowVersion:
        with SessionLocal() as db:
            db.add(workflow)
            db.commit()
            db.refresh(workflow)
        return workflow

    def get_active_workflow(self, name: str) -> WorkflowVersion | None:
        with SessionLocal() as db:
            return (
                db.query(WorkflowVersion)
                .filter(WorkflowVersion.name == name, WorkflowVersion.is_active == True)  # noqa: E712
                .first()
            )

    def store_tool_version(self, tool: ToolVersion) -> ToolVersion:
        with SessionLocal() as db:
            db.add(tool)
            db.commit()
            db.refresh(tool)
        return tool

    def get_active_tool(self, name: str) -> ToolVersion | None:
        with SessionLocal() as db:
            return (
                db.query(ToolVersion)
                .filter(ToolVersion.name == name, ToolVersion.is_active == True)  # noqa: E712
                .first()
            )

    def store_experiment_result(self, experiment: Experiment) -> Experiment:
        with SessionLocal() as db:
            db.add(experiment)
            db.commit()
            db.refresh(experiment)
        return experiment

    def get_experiment_history(self, limit: int = 50) -> list[Experiment]:
        with SessionLocal() as db:
            return (
                db.query(Experiment)
                .order_by(Experiment.created_at.desc())
                .limit(limit)
                .all()
            )

    def store_benchmark(self, benchmark: Benchmark) -> Benchmark:
        with SessionLocal() as db:
            db.add(benchmark)
            db.commit()
            db.refresh(benchmark)
        return benchmark

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _store_entry(
        self,
        memory_type: str,
        key: str,
        value: dict[str, Any],
        importance: float = 0.5,
        ttl_hours: int | None = None,
        embedding_id: str | None = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            memory_type=memory_type,
            key=key,
            value=value,
            importance=importance,
            embedding_id=embedding_id,
            expires_at=(
                datetime.utcnow() + timedelta(hours=ttl_hours)
                if ttl_hours
                else None
            ),
        )
        with SessionLocal() as db:
            db.add(entry)
            db.commit()
            db.refresh(entry)
        return entry

    def _create_embedding(
        self, key: str, text: str, metadata: dict[str, Any]
    ) -> str | None:
        """Create a vector embedding for semantic search. Falls back gracefully."""
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            if self._vector_store is None:
                self._vector_store = chromadb.PersistentClient(
                    path=settings.VECTOR_DB_PATH
                ).get_or_create_collection(
                    name=settings.SEMANTIC_MEMORY_COLLECTION,
                    embedding_function=embedding_functions.DefaultEmbeddingFunction(),
                )

            embedding_id = f"emb_{key}_{int(time.time())}"
            self._vector_store.add(
                ids=[embedding_id],
                documents=[text],
                metadatas=[metadata],
            )
            return embedding_id
        except Exception as exc:
            logger.warning("embedding.creation.failed", error=str(exc))
            return None
