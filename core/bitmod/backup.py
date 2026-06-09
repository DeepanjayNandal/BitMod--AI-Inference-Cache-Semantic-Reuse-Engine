"""Bitmod Backup — persistent context window.

Saves full query/response history as a reusable context store. Sessions can
be resumed, exported, merged, or used to seed new deployments.

The backup is NOT a database dump — it's a structured, append-only journal
of every interaction (queries, answers, cache events, ingestion events). This
creates a "context window" that is effectively unlimited in size because it's
stored on disk, not in LLM memory.

Usage:
    from bitmod.backup import BackupManager

    mgr = BackupManager(path="./bitmod_backup")
    session_id = mgr.new_session("project-research")
    mgr.record_query(session_id, question, result)
    mgr.record_ingest(session_id, ingest_result)

    # Resume later
    history = mgr.get_session(session_id)
    context = mgr.build_context(session_id, limit=50)

    # Export / import
    mgr.export_session(session_id, "backup.jsonl.gz")
    mgr.import_session("backup.jsonl.gz")
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bitmod.crypto import decrypt_if_needed, encrypt_if_enabled

logger = logging.getLogger(__name__)


@dataclass
class BackupEntry:
    """A single entry in the backup journal."""

    id: str = ""
    session_id: str = ""
    timestamp: float = 0.0
    event_type: str = ""  # query, ingest, cache_hit, cache_miss, error
    question: str = ""
    answer: str = ""
    cached: bool = False
    model_used: str = ""
    generation_ms: int = 0
    sources: list[dict] = field(default_factory=list)
    cache_layer: str = ""
    pipeline_trace: list[dict] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    filters: dict = field(default_factory=dict)
    intent: str = ""
    confidence: float | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BackupEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BackupSession:
    """Metadata for a backup session."""

    id: str = ""
    name: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    entry_count: int = 0
    total_queries: int = 0
    total_cache_hits: int = 0
    total_ingestions: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BackupSession:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class BackupManager:
    """Manages persistent context backups.

    Storage format:
        backup_path/
            sessions.json          — session index
            sessions/
                {session_id}.jsonl — append-only journal per session
    """

    def __init__(self, path: str = "./bitmod_backup", compress: bool = True, max_sessions: int = 100) -> None:
        self._path = Path(path)
        self._compress = compress
        self._max_sessions = max_sessions
        self._sessions_dir = self._path / "sessions"
        self._index_path = self._path / "sessions.json"
        self._sessions: dict[str, BackupSession] = {}
        self._initialized = False

    _SESSION_ID_RE = re.compile(r"^[a-f0-9]{12}$")

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """Validate session ID format to prevent path traversal."""
        if not BackupManager._SESSION_ID_RE.match(session_id):
            raise ValueError(f"Invalid session_id {session_id!r}: must match ^[a-f0-9]{{12}}$")

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._path.mkdir(parents=True, exist_ok=True)
        self._sessions_dir.mkdir(exist_ok=True)
        if self._index_path.exists():
            try:
                data = json.loads(self._index_path.read_text())
                for s in data.get("sessions", []):
                    session = BackupSession.from_dict(s)
                    self._sessions[session.id] = session
            except (json.JSONDecodeError, KeyError):
                logger.warning("Corrupt backup index at %s, starting fresh", self._index_path)
        self._initialized = True

    def _save_index(self) -> None:
        data = {"sessions": [s.to_dict() for s in self._sessions.values()]}
        self._index_path.write_text(json.dumps(data, indent=2))

    def _session_file(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.jsonl"

    # -------------------------------------------------------------------
    # Session management
    # -------------------------------------------------------------------

    def new_session(self, name: str = "", tags: list[str] | None = None) -> str:
        """Create a new backup session. Returns session_id."""
        self._ensure_init()

        # Enforce max sessions — remove oldest
        if len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions.values(), key=lambda s: s.updated_at)
            self.delete_session(oldest.id)

        session_id = uuid.uuid4().hex[:12]
        now = time.time()
        session = BackupSession(
            id=session_id,
            name=name or f"session-{session_id[:6]}",
            created_at=now,
            updated_at=now,
            tags=tags or [],
        )
        self._sessions[session_id] = session
        self._save_index()
        return session_id

    def get_session(self, session_id: str) -> BackupSession | None:
        """Get session metadata."""
        self._validate_session_id(session_id)
        self._ensure_init()
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[BackupSession]:
        """List all sessions, most recent first."""
        self._ensure_init()
        return sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its journal."""
        self._validate_session_id(session_id)
        self._ensure_init()
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        journal = self._session_file(session_id)
        if journal.exists():
            journal.unlink()
        self._save_index()
        return True

    # -------------------------------------------------------------------
    # Recording events
    # -------------------------------------------------------------------

    def _append(self, session_id: str, entry: BackupEntry) -> None:
        """Append an entry to the session journal."""
        self._validate_session_id(session_id)
        self._ensure_init()
        entry.id = entry.id or uuid.uuid4().hex[:16]
        entry.session_id = session_id
        entry.timestamp = entry.timestamp or time.time()

        # Encrypt sensitive fields if encryption is enabled
        entry.question = encrypt_if_enabled(entry.question) if entry.question else entry.question
        entry.answer = encrypt_if_enabled(entry.answer) if entry.answer else entry.answer

        journal = self._session_file(session_id)
        with open(journal, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        # Update session metadata
        session = self._sessions.get(session_id)
        if session:
            session.updated_at = entry.timestamp
            session.entry_count += 1
            if entry.event_type == "query":
                session.total_queries += 1
            elif entry.event_type == "cache_hit":
                session.total_cache_hits += 1
            elif entry.event_type == "ingest":
                session.total_ingestions += 1
            self._save_index()

    def record_query(
        self,
        session_id: str,
        question: str,
        answer: str,
        cached: bool = False,
        model_used: str = "",
        generation_ms: int = 0,
        sources: list[dict] | None = None,
        metadata: dict | None = None,
        cache_layer: str = "",
        pipeline_trace: list[dict] | None = None,
        token_usage: dict | None = None,
        filters: dict | None = None,
        intent: str = "",
        confidence: float | None = None,
    ) -> str:
        """Record a query event with full pipeline stats. Returns entry_id."""
        entry = BackupEntry(
            event_type="cache_hit" if cached else "query",
            question=question,
            answer=answer,
            cached=cached,
            model_used=model_used,
            generation_ms=generation_ms,
            sources=sources or [],
            cache_layer=cache_layer,
            pipeline_trace=pipeline_trace or [],
            token_usage=token_usage or {},
            filters=filters or {},
            intent=intent,
            confidence=confidence,
            metadata=metadata or {},
        )
        self._append(session_id, entry)
        return entry.id

    def record_ingest(
        self,
        session_id: str,
        document_id: str,
        title: str,
        sections: int = 0,
        chunks: int = 0,
        metadata: dict | None = None,
    ) -> str:
        """Record an ingestion event. Returns entry_id."""
        entry = BackupEntry(
            event_type="ingest",
            metadata={
                "document_id": document_id,
                "title": title,
                "sections": sections,
                "chunks": chunks,
                **(metadata or {}),
            },
        )
        self._append(session_id, entry)
        return entry.id

    def record_error(self, session_id: str, question: str, error: str, metadata: dict | None = None) -> str:
        """Record an error event. Returns entry_id."""
        entry = BackupEntry(
            event_type="error",
            question=question,
            metadata={"error": error, **(metadata or {})},
        )
        self._append(session_id, entry)
        return entry.id

    # -------------------------------------------------------------------
    # Reading history
    # -------------------------------------------------------------------

    def get_entries(self, session_id: str, limit: int = 0, event_type: str | None = None) -> list[BackupEntry]:
        """Read entries from a session journal.

        Args:
            session_id: Session to read.
            limit: Max entries to return (0 = all). Returns most recent first.
            event_type: Filter by event type (query, cache_hit, ingest, error).
        """
        self._validate_session_id(session_id)
        self._ensure_init()
        journal = self._session_file(session_id)
        if not journal.exists():
            return []

        entries = []
        with open(journal) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = BackupEntry.from_dict(json.loads(line))
                    if event_type and entry.event_type != event_type:
                        continue
                    # Decrypt sensitive fields if encrypted
                    entry.question = decrypt_if_needed(entry.question) if entry.question else entry.question
                    entry.answer = decrypt_if_needed(entry.answer) if entry.answer else entry.answer
                    entries.append(entry)
                except (json.JSONDecodeError, TypeError):
                    continue

        entries.reverse()  # Most recent first
        if limit > 0:
            entries = entries[:limit]
        return entries

    def build_context(self, session_id: str, limit: int = 50, include_sources: bool = False) -> str:
        """Build a context string from session history.

        This creates a text representation of the session's Q&A history
        that can be fed into an LLM prompt as background context.

        Args:
            session_id: Session to build context from.
            limit: Max Q&A pairs to include.
            include_sources: Whether to include source citations.

        Returns:
            Formatted context string.
        """
        entries = self.get_entries(session_id, limit=limit, event_type=None)
        # Filter to queries only, reverse to chronological order
        qa_entries = [e for e in reversed(entries) if e.event_type in ("query", "cache_hit")]

        if not qa_entries:
            return ""

        parts = []
        for entry in qa_entries:
            part = f"Q: {entry.question}\nA: {entry.answer}"
            if include_sources and entry.sources:
                citations = [s.get("citation", s.get("title", "")) for s in entry.sources[:3]]
                citations = [c for c in citations if c]
                if citations:
                    part += f"\nSources: {', '.join(citations)}"
            parts.append(part)

        return "\n\n---\n\n".join(parts)

    # -------------------------------------------------------------------
    # Export / Import
    # -------------------------------------------------------------------

    def export_session(self, session_id: str, output_path: str) -> int:
        """Export a session to a compressed JSONL file. Returns entry count."""
        self._validate_session_id(session_id)
        self._ensure_init()
        journal = self._session_file(session_id)
        if not journal.exists():
            return 0

        session = self._sessions.get(session_id)
        out = Path(output_path)

        # Write session metadata + entries (decrypt on export so exports are portable)
        opener = gzip.open if out.suffix == ".gz" or self._compress else open
        count = 0
        with opener(out, "wt") as f:
            # First line = session metadata
            if session:
                f.write(json.dumps({"__session__": session.to_dict()}) + "\n")
            with open(journal) as src:
                for line in src:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("question"):
                            data["question"] = decrypt_if_needed(data["question"])
                        if data.get("answer"):
                            data["answer"] = decrypt_if_needed(data["answer"])
                        f.write(json.dumps(data) + "\n")
                    except (json.JSONDecodeError, TypeError):
                        f.write(line + "\n")
                    count += 1

        return count

    def import_session(self, input_path: str) -> str | None:
        """Import a session from a JSONL file. Returns new session_id."""
        self._ensure_init()
        inp = Path(input_path)
        if not inp.exists():
            return None

        opener = gzip.open if inp.suffix == ".gz" else open

        session_meta: dict[str, Any] = {}
        entries: list[str] = []

        with opener(inp, "rt") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "__session__" in data:
                        session_meta = data["__session__"]
                    else:
                        entries.append(line)
                except json.JSONDecodeError:
                    continue

        if not entries:
            return None

        # Create new session
        name = session_meta.get("name", f"imported-{inp.stem}")
        tags = session_meta.get("tags", ["imported"])
        if "imported" not in tags:
            tags.append("imported")
        session_id = self.new_session(name=name, tags=tags)

        # Write entries
        journal = self._session_file(session_id)
        with open(journal, "w") as f:
            for line in entries:
                f.write(line + "\n")

        # Update counts
        session = self._sessions[session_id]
        for line in entries:
            try:
                data = json.loads(line)
                session.entry_count += 1
                et = data.get("event_type", "")
                if et == "query":
                    session.total_queries += 1
                elif et == "cache_hit":
                    session.total_cache_hits += 1
                elif et == "ingest":
                    session.total_ingestions += 1
            except json.JSONDecodeError:
                pass
        self._save_index()

        return session_id
