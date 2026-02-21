"""Cache Qualification Layer — post-match validation before serving cached responses.

Ensures cached answers are appropriate for the current request context.
This is a purely additive gate that sits between cache lookup and cache serve.
It never modifies the cache — it only decides whether a hit should be served or skipped.

Primary check: context-dependent query detection. Queries like "tell me more",
"what's next", or short follow-ups with conversation history should not be served
from cache — they need the LLM to see the full conversation context.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context-Dependent Query Detection
# ---------------------------------------------------------------------------

# Phrases that indicate the query depends on conversation history.
# These should NOT be served from cache without matching conversation context.
_CONTEXT_DEPENDENT_PATTERNS = re.compile(
    r"\b("
    # Anaphoric references (pointing back to prior context)
    r"what about that|tell me more|explain that|go deeper|elaborate on that"
    r"|more about that|what do you mean|can you clarify"
    r"|what did you mean|why is that|how so|in what way"
    # Continuation / sequencing
    r"|what\'?s next|what else|anything else|go on|continue"
    r"|what about the other|the next one|the previous one"
    r"|and the second|and the third|the last one"
    # Pronoun-heavy queries that need antecedent resolution
    r"|what is it|what are they|who are they|where is it"
    r"|how does it work|why does it matter|is it true"
    r"|do that again|try that again|repeat that"
    r"|the same thing|like before|as you said|you mentioned"
    r"|you just said|earlier you said|back to that"
    # Conversational commands
    r"|yes|no|ok|sure|right|exactly|correct|wrong"
    r"|summarize this|summarize that|put it together"
    r")\b",
    re.IGNORECASE,
)

# Short queries with pronouns are almost always context-dependent
_SHORT_PRONOUN_RE = re.compile(
    r"^(what|where|when|who|how|why|is|are|do|does|did|can|will|would)\s+"
    r"(it|that|this|they|them|those|these|he|she|his|her)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Qualification Result
# ---------------------------------------------------------------------------


@dataclass
class QualificationResult:
    """Result of cache qualification check."""

    serve: bool = True
    reason: str = ""
    check: str = ""  # which check triggered the skip

    def to_dict(self) -> dict:
        return {"serve": self.serve, "reason": self.reason, "check": self.check}


# ---------------------------------------------------------------------------
# Individual Checks
# ---------------------------------------------------------------------------


def is_context_dependent(query: str, history: list | None = None) -> bool:
    """Detect if a query depends on conversation history to be meaningful."""
    q = query.strip()

    # Very short queries with history are almost always context-dependent
    if history and len(history) > 0 and len(q.split()) <= 3:
        return True

    # Pattern-based detection
    if _CONTEXT_DEPENDENT_PATTERNS.search(q):
        return True

    # Short queries starting with pronoun references
    if _SHORT_PRONOUN_RE.match(q):
        return True

    return False


# ---------------------------------------------------------------------------
# Main Qualification Gate
# ---------------------------------------------------------------------------


def qualify_cache_hit(
    query: str,
    cached_answer: str,
    history: list | None = None,
    **kwargs,
) -> QualificationResult:
    """Run qualification checks on a cache hit. Returns whether to serve it.

    This function is fast (no I/O, no LLM calls, pure regex + string checks)
    and should be called after a cache hit is found but before serving.

    Args:
        query: The user's current query.
        cached_answer: The cached answer text.
        history: Conversation history (list of message objects).

    Returns:
        QualificationResult with serve=True if the hit should be served,
        or serve=False with a reason explaining why it was skipped.
    """
    if is_context_dependent(query, history):
        return QualificationResult(
            serve=False,
            reason="Query appears context-dependent (requires conversation history)",
            check="context_dependent",
        )

    return QualificationResult(serve=True)
