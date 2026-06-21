"""Migration 004: Add proxy_requests tracking table.

Tracks per-API-key usage of the Bitmod proxy/gateway layer. Records every
request with its API key hash, endpoint, response time, token counts, and
cost estimates. Enables usage dashboards, rate-limit enforcement, and
billing reconciliation.
"""

VERSION = 4
NAME = "add_proxy_metadata"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS proxy_requests (
    id TEXT PRIMARY KEY,
    api_key_hash TEXT NOT NULL,
    api_key_name TEXT NOT NULL DEFAULT '',
    endpoint TEXT NOT NULL DEFAULT '',
    method TEXT NOT NULL DEFAULT 'POST',
    status_code INTEGER NOT NULL DEFAULT 200,
    request_tokens INTEGER NOT NULL DEFAULT 0,
    response_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    model_used TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    client_ip TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_proxy_key_hash ON proxy_requests(api_key_hash);
CREATE INDEX IF NOT EXISTS idx_proxy_created ON proxy_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_proxy_key_created ON proxy_requests(api_key_hash, created_at);
CREATE INDEX IF NOT EXISTS idx_proxy_endpoint ON proxy_requests(endpoint);

CREATE TABLE IF NOT EXISTS api_key_quotas (
    api_key_hash TEXT PRIMARY KEY,
    api_key_name TEXT NOT NULL DEFAULT '',
    daily_request_limit INTEGER NOT NULL DEFAULT 1000,
    daily_token_limit INTEGER NOT NULL DEFAULT 1000000,
    monthly_cost_limit_usd REAL NOT NULL DEFAULT 100.0,
    rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS proxy_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_key_hash VARCHAR(64) NOT NULL,
    api_key_name VARCHAR(255) NOT NULL DEFAULT '',
    endpoint VARCHAR(500) NOT NULL DEFAULT '',
    method VARCHAR(10) NOT NULL DEFAULT 'POST',
    status_code INTEGER NOT NULL DEFAULT 200,
    request_tokens INTEGER NOT NULL DEFAULT 0,
    response_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    model_used VARCHAR(100) NOT NULL DEFAULT '',
    provider VARCHAR(50) NOT NULL DEFAULT '',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd FLOAT NOT NULL DEFAULT 0.0,
    cache_hit BOOLEAN NOT NULL DEFAULT false,
    error_message TEXT,
    client_ip INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxy_key_hash ON proxy_requests(api_key_hash);
CREATE INDEX IF NOT EXISTS idx_proxy_created ON proxy_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_proxy_key_created ON proxy_requests(api_key_hash, created_at);
CREATE INDEX IF NOT EXISTS idx_proxy_endpoint ON proxy_requests(endpoint);

CREATE TABLE IF NOT EXISTS api_key_quotas (
    api_key_hash VARCHAR(64) PRIMARY KEY,
    api_key_name VARCHAR(255) NOT NULL DEFAULT '',
    daily_request_limit INTEGER NOT NULL DEFAULT 1000,
    daily_token_limit INTEGER NOT NULL DEFAULT 1000000,
    monthly_cost_limit_usd FLOAT NOT NULL DEFAULT 100.0,
    rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS proxy_requests (
    id CHAR(36) PRIMARY KEY,
    api_key_hash VARCHAR(64) NOT NULL,
    api_key_name VARCHAR(255) NOT NULL DEFAULT '',
    endpoint VARCHAR(500) NOT NULL DEFAULT '',
    method VARCHAR(10) NOT NULL DEFAULT 'POST',
    status_code INT NOT NULL DEFAULT 200,
    request_tokens INT NOT NULL DEFAULT 0,
    response_tokens INT NOT NULL DEFAULT 0,
    total_tokens INT NOT NULL DEFAULT 0,
    model_used VARCHAR(100) NOT NULL DEFAULT '',
    provider VARCHAR(50) NOT NULL DEFAULT '',
    latency_ms INT NOT NULL DEFAULT 0,
    estimated_cost_usd FLOAT NOT NULL DEFAULT 0.0,
    cache_hit TINYINT NOT NULL DEFAULT 0,
    error_message TEXT,
    client_ip VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_proxy_key_hash ON proxy_requests(api_key_hash);
CREATE INDEX idx_proxy_created ON proxy_requests(created_at);
CREATE INDEX idx_proxy_key_created ON proxy_requests(api_key_hash, created_at);
CREATE INDEX idx_proxy_endpoint ON proxy_requests(endpoint);

CREATE TABLE IF NOT EXISTS api_key_quotas (
    api_key_hash VARCHAR(64) PRIMARY KEY,
    api_key_name VARCHAR(255) NOT NULL DEFAULT '',
    daily_request_limit INT NOT NULL DEFAULT 1000,
    daily_token_limit INT NOT NULL DEFAULT 1000000,
    monthly_cost_limit_usd FLOAT NOT NULL DEFAULT 100.0,
    rate_limit_rpm INT NOT NULL DEFAULT 60,
    is_active TINYINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def apply_mongodb(db):
    """Create proxy_requests and api_key_quotas collections with indexes."""
    # proxy_requests
    if "proxy_requests" not in db.list_collection_names():
        db.create_collection("proxy_requests")
    pr = db["proxy_requests"]
    pr.create_index("api_key_hash")
    pr.create_index("created_at")
    pr.create_index([("api_key_hash", 1), ("created_at", -1)])
    pr.create_index("endpoint")

    # api_key_quotas
    if "api_key_quotas" not in db.list_collection_names():
        db.create_collection("api_key_quotas")
    akq = db["api_key_quotas"]
    akq.create_index("api_key_hash", unique=True)
