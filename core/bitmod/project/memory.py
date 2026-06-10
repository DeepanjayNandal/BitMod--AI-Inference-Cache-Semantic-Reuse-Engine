"""Conversation memory — records, searches, and learns from past conversations."""

from __future__ import annotations

import logging
from typing import Any

from bitmod.interfaces.database import (
    ConversationRecord,
    CorrectionRecord,
    DatabaseBackend,
)

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manages conversation history and user corrections for learning.

    Records every Q&A exchange, optionally with embeddings for semantic
    retrieval. Users can rate responses and submit corrections that
    improve future answers.
    """

    def __init__(self, db: DatabaseBackend, embed_fn: Any = None):
        """
        Args:
            db: Database backend.
            embed_fn: Optional callable(texts: list[str]) -> list[list[float]].
        """
        self._db = db
        self._embed_fn = embed_fn

    def record(
        self,
        user_message: str,
        assistant_response: str,
        model_used: str = "",
        cache_hit: bool = False,
        generation_ms: int = 0,
        project_id: str | None = None,
        context_used: list[dict] | None = None,
    ) -> ConversationRecord:
        """Record a conversation exchange. Returns the stored record."""
        conv = ConversationRecord(
            project_id=project_id,
            user_message=user_message,
            assistant_response=assistant_response,
            model_used=model_used,
            cache_hit=cache_hit,
            generation_ms=generation_ms,
            context_used=context_used or [],
        )

        with self._db.session() as s:
            self._db.conversation_store(s, conv)

            # Store embedding if available
            if self._embed_fn:
                try:
                    emb = self._embed_fn([user_message])
                    if emb and emb[0]:
                        self._db.conversation_store_embedding(s, conv.id, emb[0])
                except Exception:
                    logger.warning("Failed to embed conversation %s", conv.id)

        return conv

    def search(
        self,
        query: str,
        project_id: str | None = None,
        limit: int = 5,
    ) -> list[ConversationRecord]:
        """Find similar past conversations by semantic search.

        Falls back to recent conversations if no embedding function.
        """
        with self._db.session() as s:
            if self._embed_fn:
                try:
                    emb = self._embed_fn([query])
                    if emb and emb[0]:
                        return self._db.conversation_search(
                            s,
                            emb[0],
                            project_id=project_id,
                            limit=limit,
                        )
                except Exception:
                    logger.warning("Conversation search embedding failed")

            # Fallback: return recent
            return self._db.conversation_list(
                s,
                project_id=project_id,
                limit=limit,
            )

    def list_recent(
        self,
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationRecord]:
        """List recent conversations."""
        with self._db.session() as s:
            return self._db.conversation_list(
                s,
                project_id=project_id,
                limit=limit,
                offset=offset,
            )

    def rate(self, conversation_id: str, rating: int, feedback: str = "") -> None:
        """Rate a conversation (1-5) with optional feedback."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be 1-5")
        with self._db.session() as s:
            self._db.conversation_rate(s, conversation_id, rating, feedback)

    def correct(
        self,
        conversation_id: str,
        corrected_answer: str,
        correction_type: str = "factual",
        project_id: str | None = None,
        status: str = "pending",
    ) -> CorrectionRecord:
        """Submit a correction for a conversation response.

        The correction is stored and can be used to improve future answers
        by injecting relevant corrections into the context. Only corrections
        with status='approved' are included in LLM context assembly.

        Args:
            status: Initial status. 'pending' (default) or 'approved' for admin users.
        """
        if status not in ("pending", "approved", "rejected"):
            status = "pending"

        with self._db.session() as s:
            conv = self._db.conversation_get(s, conversation_id)
            if not conv:
                raise ValueError(f"Conversation not found: {conversation_id}")

            correction = CorrectionRecord(
                conversation_id=conversation_id,
                project_id=project_id or conv.project_id,
                original_question=conv.user_message,
                original_answer=conv.assistant_response,
                corrected_answer=corrected_answer,
                correction_type=correction_type,
                status=status,
            )

            # Embed the correction for semantic retrieval
            if self._embed_fn:
                try:
                    emb = self._embed_fn([conv.user_message])
                    if emb and emb[0]:
                        correction.embedding = emb[0]
                except Exception:
                    logger.warning("Failed to embed correction")

            self._db.correction_store(s, correction)
            return correction

    def find_corrections(
        self,
        query: str,
        project_id: str | None = None,
        limit: int = 5,
    ) -> list[CorrectionRecord]:
        """Find relevant corrections for a query."""
        with self._db.session() as s:
            if self._embed_fn:
                try:
                    emb = self._embed_fn([query])
                    if emb and emb[0]:
                        return self._db.correction_search(
                            s,
                            emb[0],
                            project_id=project_id,
                            limit=limit,
                        )
                except Exception:
                    logger.warning("Correction search embedding failed")

            # Fallback: return recent corrections
            return self._db.correction_list(
                s,
                project_id=project_id,
                limit=limit,
            )

    def list_corrections(
        self,
        project_id: str | None = None,
        applied_only: bool = False,
        limit: int = 50,
    ) -> list[CorrectionRecord]:
        """List corrections."""
        with self._db.session() as s:
            return self._db.correction_list(
                s,
                project_id=project_id,
                applied_only=applied_only,
                limit=limit,
            )
