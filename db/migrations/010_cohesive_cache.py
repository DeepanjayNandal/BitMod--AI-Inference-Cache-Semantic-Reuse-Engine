"""Migration 010: Add cohesive cache tables.

Creates three tables for the cohesive cache engine:
- similarity_links: learned relationships between near-miss cache entries
- atomic_facts: reusable facts decomposed from LLM-generated answers
- atomic_fact_embeddings: vector embeddings for semantic fact search

All CREATE statements are idempotent (IF NOT EXISTS).
"""

from __future__ import annotations

VERSION = 10
NAME = "cohesive_cache"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS similarity_links (
    id TEXT PRIMARY KEY,
    source_cache_id TEXT NOT NULL,
    target_cache_id TEXT NOT NULL,
    similarity REAL NOT NULL,
    source_query_norm TEXT NOT NULL,
    target_query_norm TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sim_links_source ON similarity_links(source_cache_id);
CREATE INDEX IF NOT EXISTS idx_sim_links_target ON similarity_links(target_cache_id);

CREATE TABLE IF NOT EXISTS atomic_facts (
    id TEXT PRIMARY KEY,
    source_cache_id TEXT NOT NULL,
    fact_text TEXT NOT NULL,
    entity TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    confidence REAL NOT NULL DEFAULT 1.0,
    serve_count INTEGER NOT NULL DEFAULT 0,
    namespace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_entity ON atomic_facts(entity);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_namespace ON atomic_facts(namespace_id);

CREATE TABLE IF NOT EXISTS atomic_fact_embeddings (
    fact_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL
);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS similarity_links (
    id TEXT PRIMARY KEY,
    source_cache_id TEXT NOT NULL,
    target_cache_id TEXT NOT NULL,
    similarity REAL NOT NULL,
    source_query_norm TEXT NOT NULL,
    target_query_norm TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (now())
);
CREATE INDEX IF NOT EXISTS idx_sim_links_source ON similarity_links(source_cache_id);
CREATE INDEX IF NOT EXISTS idx_sim_links_target ON similarity_links(target_cache_id);

CREATE TABLE IF NOT EXISTS atomic_facts (
    id TEXT PRIMARY KEY,
    source_cache_id TEXT NOT NULL,
    fact_text TEXT NOT NULL,
    entity TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    confidence REAL NOT NULL DEFAULT 1.0,
    serve_count INTEGER NOT NULL DEFAULT 0,
    namespace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (now())
);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_entity ON atomic_facts(entity);
CREATE INDEX IF NOT EXISTS idx_atomic_facts_namespace ON atomic_facts(namespace_id);

CREATE TABLE IF NOT EXISTS atomic_fact_embeddings (
    fact_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL
);
"""


def run_sqlite(conn) -> None:  # noqa: ANN001
    """Apply migration to a SQLite connection."""
    conn.executescript(SQL_SQLITE)


def run_postgres(conn) -> None:  # noqa: ANN001
    """Apply migration to a PostgreSQL connection."""
    conn.execute(SQL_POSTGRESQL)
