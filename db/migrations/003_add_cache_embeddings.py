"""Migration 003: Add cache_embeddings table.

Stores query embeddings alongside answer_cache entries to enable semantic
(vector-similarity) cache lookups. FK references answer_cache(id) so
embeddings are automatically scoped to valid cache entries.
"""

VERSION = 3
NAME = "add_cache_embeddings"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS cache_embeddings (
    cache_id TEXT PRIMARY KEY REFERENCES answer_cache(id),
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS cache_embeddings (
    cache_id UUID PRIMARY KEY REFERENCES answer_cache(id) ON DELETE CASCADE,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cache_embeddings_vector
    ON cache_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);
"""

# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS cache_embeddings (
    cache_id CHAR(36) PRIMARY KEY,
    embedding LONGBLOB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cache_id) REFERENCES answer_cache(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def apply_mongodb(db):
    """Create cache_embeddings collection with indexes."""
    if "cache_embeddings" not in db.list_collection_names():
        db.create_collection("cache_embeddings")
    ce = db["cache_embeddings"]
    ce.create_index("cache_id", unique=True)
