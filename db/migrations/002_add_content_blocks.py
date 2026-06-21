"""Migration 002: Add content_blocks, section_tags, and section_relationships tables.

These tables support multi-compression content representations, faceted
retrieval via structured tags, and section-to-section relationship tracking
(co-retrieval, citations, supersession).
"""

VERSION = 2
NAME = "add_content_blocks"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS content_blocks (
    id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL REFERENCES sections(id),
    compression TEXT NOT NULL DEFAULT 'full',
    content TEXT NOT NULL DEFAULT '',
    version_hash TEXT NOT NULL DEFAULT '',
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS section_tags (
    section_id TEXT NOT NULL REFERENCES sections(id),
    tag_key TEXT NOT NULL,
    tag_value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'rule',
    PRIMARY KEY (section_id, tag_key, tag_value)
);

CREATE TABLE IF NOT EXISTS section_relationships (
    section_a_id TEXT NOT NULL REFERENCES sections(id),
    section_b_id TEXT NOT NULL REFERENCES sections(id),
    relationship TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'co_retrieval',
    hit_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (section_a_id, section_b_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_blocks_section ON content_blocks(section_id);
CREATE INDEX IF NOT EXISTS idx_blocks_section_compression ON content_blocks(section_id, compression);
CREATE INDEX IF NOT EXISTS idx_tags_section ON section_tags(section_id);
CREATE INDEX IF NOT EXISTS idx_tags_key_value ON section_tags(tag_key, tag_value);
CREATE INDEX IF NOT EXISTS idx_rels_a ON section_relationships(section_a_id);
CREATE INDEX IF NOT EXISTS idx_rels_b ON section_relationships(section_b_id);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS content_blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    section_id UUID NOT NULL REFERENCES sections(id),
    compression VARCHAR(50) NOT NULL DEFAULT 'full',
    content TEXT NOT NULL DEFAULT '',
    version_hash VARCHAR(64) NOT NULL DEFAULT '',
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS section_tags (
    section_id UUID NOT NULL REFERENCES sections(id),
    tag_key VARCHAR(100) NOT NULL,
    tag_value VARCHAR(500) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    source VARCHAR(50) NOT NULL DEFAULT 'rule',
    PRIMARY KEY (section_id, tag_key, tag_value)
);

CREATE TABLE IF NOT EXISTS section_relationships (
    section_a_id UUID NOT NULL REFERENCES sections(id),
    section_b_id UUID NOT NULL REFERENCES sections(id),
    relationship VARCHAR(50) NOT NULL,
    strength FLOAT NOT NULL DEFAULT 1.0,
    source VARCHAR(50) NOT NULL DEFAULT 'co_retrieval',
    hit_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (section_a_id, section_b_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_blocks_section ON content_blocks(section_id);
CREATE INDEX IF NOT EXISTS idx_blocks_section_compression ON content_blocks(section_id, compression);
CREATE INDEX IF NOT EXISTS idx_tags_section ON section_tags(section_id);
CREATE INDEX IF NOT EXISTS idx_tags_key_value ON section_tags(tag_key, tag_value);
CREATE INDEX IF NOT EXISTS idx_rels_a ON section_relationships(section_a_id);
CREATE INDEX IF NOT EXISTS idx_rels_b ON section_relationships(section_b_id);
"""

# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS content_blocks (
    id CHAR(36) PRIMARY KEY,
    section_id CHAR(36) NOT NULL,
    compression VARCHAR(50) NOT NULL DEFAULT 'full',
    content LONGTEXT NOT NULL,
    version_hash VARCHAR(64) NOT NULL DEFAULT '',
    token_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (section_id) REFERENCES sections(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS section_tags (
    section_id CHAR(36) NOT NULL,
    tag_key VARCHAR(100) NOT NULL,
    tag_value VARCHAR(500) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    source VARCHAR(50) NOT NULL DEFAULT 'rule',
    PRIMARY KEY (section_id, tag_key, tag_value(191)),
    FOREIGN KEY (section_id) REFERENCES sections(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS section_relationships (
    section_a_id CHAR(36) NOT NULL,
    section_b_id CHAR(36) NOT NULL,
    relationship VARCHAR(50) NOT NULL,
    strength FLOAT NOT NULL DEFAULT 1.0,
    source VARCHAR(50) NOT NULL DEFAULT 'co_retrieval',
    hit_count INT NOT NULL DEFAULT 1,
    PRIMARY KEY (section_a_id, section_b_id, relationship),
    FOREIGN KEY (section_a_id) REFERENCES sections(id),
    FOREIGN KEY (section_b_id) REFERENCES sections(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_blocks_section ON content_blocks(section_id);
CREATE INDEX idx_blocks_section_compression ON content_blocks(section_id, compression);
CREATE INDEX idx_tags_section ON section_tags(section_id);
CREATE INDEX idx_tags_key_value ON section_tags(tag_key, tag_value(191));
CREATE INDEX idx_rels_a ON section_relationships(section_a_id);
CREATE INDEX idx_rels_b ON section_relationships(section_b_id);
"""


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def apply_mongodb(db):
    """Create collections and indexes for content blocks, tags, and relationships."""
    # content_blocks
    if "content_blocks" not in db.list_collection_names():
        db.create_collection("content_blocks")
    cb = db["content_blocks"]
    cb.create_index("section_id")
    cb.create_index([("section_id", 1), ("compression", 1)])

    # section_tags
    if "section_tags" not in db.list_collection_names():
        db.create_collection("section_tags")
    st = db["section_tags"]
    st.create_index("section_id")
    st.create_index([("tag_key", 1), ("tag_value", 1)])
    st.create_index(
        [("section_id", 1), ("tag_key", 1), ("tag_value", 1)],
        unique=True,
    )

    # section_relationships
    if "section_relationships" not in db.list_collection_names():
        db.create_collection("section_relationships")
    sr = db["section_relationships"]
    sr.create_index("section_a_id")
    sr.create_index("section_b_id")
    sr.create_index(
        [("section_a_id", 1), ("section_b_id", 1), ("relationship", 1)],
        unique=True,
    )
