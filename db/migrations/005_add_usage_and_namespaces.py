"""Migration 005: Add usage_tracking and namespaces tables.

usage_tracking: Aggregated per-key daily usage stats for billing and dashboards.
namespaces: Multi-tenant data isolation — each namespace gets its own document scope.
"""

VERSION = 5
NAME = "add_usage_and_namespaces"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS usage_tracking (
    id TEXT PRIMARY KEY,
    api_key_hash TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    request_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    cache_misses INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(api_key_hash, date)
);

CREATE INDEX IF NOT EXISTS idx_usage_key_date ON usage_tracking(api_key_hash, date);
CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_tracking(date);

CREATE TABLE IF NOT EXISTS namespaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    owner TEXT NOT NULL DEFAULT 'system',
    is_active INTEGER NOT NULL DEFAULT 1,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_namespaces_name ON namespaces(name);
CREATE INDEX IF NOT EXISTS idx_namespaces_owner ON namespaces(owner);

-- Add namespace_id column to documents if it doesn't exist.
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we handle
-- this gracefully in the migration runner (errors on duplicate are caught).
ALTER TABLE documents ADD COLUMN namespace_id TEXT DEFAULT NULL REFERENCES namespaces(id);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS usage_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_key_hash VARCHAR(64) NOT NULL DEFAULT '',
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    request_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    cache_misses INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(api_key_hash, date)
);

CREATE INDEX IF NOT EXISTS idx_usage_key_date ON usage_tracking(api_key_hash, date);
CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_tracking(date);

CREATE TABLE IF NOT EXISTS namespaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    owner VARCHAR(255) NOT NULL DEFAULT 'system',
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_namespaces_name ON namespaces(name);
CREATE INDEX IF NOT EXISTS idx_namespaces_owner ON namespaces(owner);

DO $$ BEGIN
    ALTER TABLE documents ADD COLUMN IF NOT EXISTS namespace_id UUID REFERENCES namespaces(id);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
"""

# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS usage_tracking (
    id CHAR(36) PRIMARY KEY,
    api_key_hash VARCHAR(64) NOT NULL DEFAULT '',
    date DATE NOT NULL,
    request_count INT NOT NULL DEFAULT 0,
    token_count INT NOT NULL DEFAULT 0,
    cache_hits INT NOT NULL DEFAULT 0,
    cache_misses INT NOT NULL DEFAULT 0,
    estimated_cost_usd FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_usage_key_date (api_key_hash, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_usage_key_date ON usage_tracking(api_key_hash, date);
CREATE INDEX idx_usage_date ON usage_tracking(date);

CREATE TABLE IF NOT EXISTS namespaces (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    owner VARCHAR(255) NOT NULL DEFAULT 'system',
    is_active TINYINT NOT NULL DEFAULT 1,
    metadata JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_namespaces_name ON namespaces(name);
CREATE INDEX idx_namespaces_owner ON namespaces(owner);
"""


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def apply_mongodb(db):
    """Create usage_tracking and namespaces collections with indexes."""
    # usage_tracking
    if "usage_tracking" not in db.list_collection_names():
        db.create_collection("usage_tracking")
    ut = db["usage_tracking"]
    ut.create_index([("api_key_hash", 1), ("date", 1)], unique=True)
    ut.create_index("date")

    # namespaces
    if "namespaces" not in db.list_collection_names():
        db.create_collection("namespaces")
    ns = db["namespaces"]
    ns.create_index("name", unique=True)
    ns.create_index("owner")
