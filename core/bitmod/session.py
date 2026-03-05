"""Session-aware caching (Layer 7).

Tracks conversation sessions in-memory to provide contextual evidence
when a query is a follow-up in an existing session.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class SessionState:
    """Tracks a single conversation session's history."""

    session_id: str
    queries: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    cache_keys: list[str] = field(default_factory=list)

    @property
    def turn_count(self) -> int:
        return len(self.queries)

    def record(self, query: str, answer: str, cache_key: str) -> None:
        self.queries.append(query)
        self.answers.append(answer)
        self.cache_keys.append(cache_key)

    def last_exchange_context(self) -> str | None:
        """Format the most recent Q&A as supplementary context."""
        if not self.queries:
            return None
        return f"Previous Q: {self.queries[-1]}\nPrevious A: {self.answers[-1]}"


class SessionTracker:
    """In-memory LRU-bounded session tracker.

    Sessions are keyed by the hash of the first user message in the
    conversation. When the tracker exceeds max_sessions, the oldest
    session is evicted.
    """

    def __init__(self, max_sessions: int = 10_000):
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()
        self._max_sessions = max_sessions
        self._instance_salt = uuid.uuid4().hex

    def _compute_session_id(self, messages: list[dict]) -> str:
        """Derive session ID from all user messages in the conversation.

        Uses the full conversation prefix (all messages) plus a per-instance
        random salt to avoid collisions between different users sending the
        same opening message.
        """
        parts: list[str] = [self._instance_salt]
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
            parts.append(f"{role}:{content}")
        if len(parts) == 1:
            parts.append("empty")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

    def get_or_create(self, messages: list[dict]) -> SessionState:
        """Get an existing session or create a new one.

        Returns the SessionState for the conversation identified by messages.
        """
        sid = self._compute_session_id(messages)
        if sid in self._sessions:
            self._sessions.move_to_end(sid)
            return self._sessions[sid]

        state = SessionState(session_id=sid)
        self._sessions[sid] = state

        # Evict oldest if over capacity
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

        return state

    def record(self, state: SessionState, query: str, answer: str, cache_key: str) -> None:
        """Record a Q&A exchange in the session."""
        state.record(query, answer, cache_key)
