"""Migration 007: Add cache TTL and eviction support.

Adds max_age_seconds and last_served_at to answer_cache for TTL-based
expiration and LRU eviction.  created_at already exists in both the
PostgreSQL and SQLite schemas so it is not touched here.

Both ALTER TABLE statements use IF NOT EXISTS–safe patterns so the
migration is idempotent.
"""

VERSION = 7
NAME = "cache_ttl"

# ---------------------------------------------------------------------------
# SQLite — no ALTER TABLE … IF NOT EXISTS, so we catch the error
# ---------------------------------------------------------------------------

SQL_SQLITE = """
-- max_age_seconds: NULL means no expiry (backwards compatible)
ALTER TABLE answer_cache ADD COLUMN max_age_seconds INTEGER DEFAULT NULL;

-- last_served_at: tracks last serve time for LRU eviction
ALTER TABLE answer_cache ADD COLUMN last_served_at TEXT DEFAULT NULL;
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRES = """
-- max_age_seconds: NULL means no expiry (backwards compatible)
ALTER TABLE answer_cache ADD COLUMN IF NOT EXISTS max_age_seconds INTEGER DEFAULT NULL;

-- last_served_at: tracks last serve time for LRU eviction
ALTER TABLE answer_cache ADD COLUMN IF NOT EXISTS last_served_at TIMESTAMPTZ DEFAULT NULL;

-- Index for efficient eviction queries (oldest served first)
CREATE INDEX IF NOT EXISTS ix_answer_cache_lru
    ON answer_cache (last_served_at ASC NULLS FIRST)
    WHERE is_valid = true;
"""


def run_sqlite(conn) -> None:  # noqa: ANN001
    """Apply migration to a SQLite connection, ignoring duplicate columns."""
    for stmt in SQL_SQLITE.strip().split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("--"):
            continue
        try:
            conn.execute(stmt)
        except Exception as exc:
            # "duplicate column name" is expected on re-run
            if "duplicate column" in str(exc).lower():
                continue
            raise


def run_postgres(conn) -> None:  # noqa: ANN001
    """Apply migration to a PostgreSQL connection (IF NOT EXISTS is idempotent)."""
    conn.execute(SQL_POSTGRES)
