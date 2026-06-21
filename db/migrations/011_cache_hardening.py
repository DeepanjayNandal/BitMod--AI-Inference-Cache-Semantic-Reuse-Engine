"""Migration 011: Cache hardening — add strength, quality_score, estimated_cost.

Adds:
- similarity_links.strength: reinforcement counter for link traversal
- atomic_facts.quality_score: heuristic quality score for fact evidence weighting
- answer_cache.estimated_cost: estimated generation cost for cost-aware eviction

All ALTER statements are idempotent (wrapped in try/except for existing columns).
"""

from __future__ import annotations

VERSION = 11
NAME = "cache_hardening"


def run_sqlite(conn) -> None:  # noqa: ANN001
    """Apply migration to a SQLite connection."""
    for stmt in [
        "ALTER TABLE similarity_links ADD COLUMN strength INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE atomic_facts ADD COLUMN quality_score REAL NOT NULL DEFAULT 0.5",
        "ALTER TABLE answer_cache ADD COLUMN estimated_cost REAL NOT NULL DEFAULT 0.0",
    ]:
        try:
            conn.execute(stmt)
        except Exception:  # noqa: S110 — column may already exist
            pass
    conn.commit()


def run_postgres(conn) -> None:  # noqa: ANN001
    """Apply migration to a PostgreSQL connection."""
    for stmt in [
        "ALTER TABLE similarity_links ADD COLUMN IF NOT EXISTS strength INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE atomic_facts ADD COLUMN IF NOT EXISTS quality_score REAL NOT NULL DEFAULT 0.5",
        "ALTER TABLE answer_cache ADD COLUMN IF NOT EXISTS estimated_cost REAL NOT NULL DEFAULT 0.0",
    ]:
        conn.execute(stmt)
