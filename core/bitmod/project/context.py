"""Context assembler — builds context from project knowledge for LLM queries.

Gathers relevant project chunks, past conversations, and corrections,
then assembles them into a context string within a token budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from bitmod.interfaces.database import DatabaseBackend

logger = logging.getLogger(__name__)

# Default token budget allocation
DEFAULT_TOKEN_BUDGET = 8000
BUDGET_PROJECT_FILES = 0.50  # 50% for project code/docs
BUDGET_HISTORY = 0.25  # 25% for relevant past conversations
BUDGET_CORRECTIONS = 0.10  # 10% for corrections
BUDGET_CACHE_CONTEXT = 0.15  # 15% for cache-retrieved context


@dataclass
class AssembledContext:
    """The assembled context ready to inject into an LLM prompt."""

    project_context: str = ""
    history_context: str = ""
    corrections_context: str = ""
    total_tokens: int = 0
    sources: list[dict] = field(default_factory=list)

    @property
    def full_context(self) -> str:
        """Combine all context sections into a single string."""
        parts = []
        if self.project_context:
            parts.append(f"## Relevant Project Code\n{self.project_context}")
        if self.corrections_context:
            parts.append(f"## Previous Corrections\n{self.corrections_context}")
        if self.history_context:
            parts.append(f"## Related Past Conversations\n{self.history_context}")
        return "\n\n".join(parts)

    @property
    def is_empty(self) -> bool:
        return not (self.project_context or self.history_context or self.corrections_context)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


class ContextAssembler:
    """Assembles context from project knowledge for LLM queries.

    Before a cache key is computed, this assembler gathers relevant
    project code, past conversations, and corrections. The assembled
    context is injected into the LLM prompt to provide project-specific
    knowledge.
    """

    def __init__(
        self,
        db: DatabaseBackend,
        embed_fn: Any = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ):
        self._db = db
        self._embed_fn = embed_fn
        self._budget = token_budget

    def assemble(
        self,
        query: str,
        project_id: str | None = None,
        include_history: bool = True,
        include_corrections: bool = True,
    ) -> AssembledContext:
        """Assemble context for a query.

        Args:
            query: The user's question.
            project_id: Optional project to scope context to.
            include_history: Whether to include past conversations.
            include_corrections: Whether to include corrections.

        Returns:
            AssembledContext with project code, history, and corrections.
        """
        ctx = AssembledContext()

        if not project_id:
            return ctx

        budget_project = int(self._budget * BUDGET_PROJECT_FILES)
        budget_history = int(self._budget * BUDGET_HISTORY) if include_history else 0
        budget_corrections = int(self._budget * BUDGET_CORRECTIONS) if include_corrections else 0

        with self._db.session() as s:
            # 1. Find relevant project chunks
            if self._embed_fn:
                try:
                    emb = self._embed_fn([query])
                    if emb and emb[0]:
                        chunks = self._db.project_chunks_search(
                            s,
                            project_id,
                            emb[0],
                            limit=15,
                        )
                        if chunks:
                            parts = []
                            tokens_used = 0
                            for chunk in chunks:
                                chunk_tokens = _estimate_tokens(chunk.content)
                                if tokens_used + chunk_tokens > budget_project:
                                    break

                                header = ""
                                if chunk.symbol_name:
                                    header = f"# {chunk.symbol_type}: {chunk.symbol_name}"
                                parts.append(
                                    f"```\n{header}\n{chunk.content}\n```\n(lines {chunk.start_line}-{chunk.end_line})"
                                )
                                tokens_used += chunk_tokens
                                ctx.sources.append(
                                    {
                                        "type": "project_chunk",
                                        "file_id": chunk.file_id,
                                        "lines": f"{chunk.start_line}-{chunk.end_line}",
                                        "symbol": chunk.symbol_name,
                                    }
                                )

                            ctx.project_context = _truncate_to_tokens(
                                "\n\n".join(parts),
                                budget_project,
                            )
                except Exception:
                    logger.warning("Project chunk search failed")

            # 2. Find relevant past conversations
            if include_history and self._embed_fn and budget_history > 0:
                try:
                    emb = self._embed_fn([query])
                    if emb and emb[0]:
                        convs = self._db.conversation_search(
                            s,
                            emb[0],
                            project_id=project_id,
                            limit=5,
                        )
                        if convs:
                            parts = []
                            tokens_used = 0
                            for conv in convs:
                                entry = f"Q: {conv.user_message}\nA: {conv.assistant_response}"
                                entry_tokens = _estimate_tokens(entry)
                                if tokens_used + entry_tokens > budget_history:
                                    break
                                parts.append(entry)
                                tokens_used += entry_tokens
                                ctx.sources.append(
                                    {
                                        "type": "conversation",
                                        "id": conv.id,
                                        "rated": conv.rating,
                                    }
                                )

                            ctx.history_context = _truncate_to_tokens(
                                "\n\n---\n\n".join(parts),
                                budget_history,
                            )
                except Exception:
                    logger.warning("Conversation search failed")

            # 3. Find relevant corrections (only approved ones to prevent poisoning)
            if include_corrections and self._embed_fn and budget_corrections > 0:
                try:
                    emb = self._embed_fn([query])
                    if emb and emb[0]:
                        corrections = self._db.correction_search(
                            s,
                            emb[0],
                            project_id=project_id,
                            limit=3,
                        )
                        # H4: Filter to only approved corrections
                        corrections = [c for c in corrections if getattr(c, "status", "approved") == "approved"]
                        if corrections:
                            parts = []
                            tokens_used = 0
                            for corr in corrections:
                                entry = (
                                    f"Original Q: {corr.original_question}\n"
                                    f"Wrong A: {corr.original_answer[:200]}...\n"
                                    f"Correct A: {corr.corrected_answer}"
                                )
                                entry_tokens = _estimate_tokens(entry)
                                if tokens_used + entry_tokens > budget_corrections:
                                    break
                                parts.append(entry)
                                tokens_used += entry_tokens
                                ctx.sources.append(
                                    {
                                        "type": "correction",
                                        "id": corr.id,
                                        "type_": corr.correction_type,
                                    }
                                )

                            ctx.corrections_context = _truncate_to_tokens(
                                "\n\n".join(parts),
                                budget_corrections,
                            )
                except Exception:
                    logger.warning("Correction search failed")

        # Calculate total tokens
        ctx.total_tokens = (
            _estimate_tokens(ctx.project_context)
            + _estimate_tokens(ctx.history_context)
            + _estimate_tokens(ctx.corrections_context)
        )

        return ctx
