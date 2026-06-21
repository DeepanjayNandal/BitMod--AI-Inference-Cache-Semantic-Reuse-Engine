"""Migration 006: Add project knowledge system tables.

Local knowledge tracking: project indexing, conversation memory, corrections,
and file chunk embeddings for context-aware AI responses.
"""

VERSION = 6
NAME = "add_project_knowledge"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    framework TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    last_scanned_at TEXT,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_chunks INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);
CREATE INDEX IF NOT EXISTS idx_projects_root ON projects(root_path);

CREATE TABLE IF NOT EXISTS project_files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    file_hash TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    last_modified TEXT NOT NULL DEFAULT '',
    is_indexed INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_pfiles_project ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_pfiles_hash ON project_files(file_hash);
CREATE INDEX IF NOT EXISTS idx_pfiles_path ON project_files(project_id, relative_path);

CREATE TABLE IF NOT EXISTS project_chunks (
    id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL REFERENCES project_files(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '',
    start_line INTEGER NOT NULL DEFAULT 0,
    end_line INTEGER NOT NULL DEFAULT 0,
    symbol_name TEXT,
    symbol_type TEXT,
    embedding BLOB,
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pchunks_file ON project_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_pchunks_project ON project_chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_pchunks_symbol ON project_chunks(symbol_name);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    user_message TEXT NOT NULL DEFAULT '',
    assistant_response TEXT NOT NULL DEFAULT '',
    model_used TEXT NOT NULL DEFAULT '',
    cache_hit INTEGER NOT NULL DEFAULT 0,
    rating INTEGER,
    feedback TEXT,
    context_used TEXT NOT NULL DEFAULT '[]',
    generation_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_rating ON conversations(rating);

CREATE TABLE IF NOT EXISTS conversation_embeddings (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    original_question TEXT NOT NULL DEFAULT '',
    original_answer TEXT NOT NULL DEFAULT '',
    corrected_answer TEXT NOT NULL DEFAULT '',
    correction_type TEXT NOT NULL DEFAULT 'factual',
    is_applied INTEGER NOT NULL DEFAULT 0,
    embedding BLOB,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_corrections_project ON corrections(project_id);
CREATE INDEX IF NOT EXISTS idx_corrections_type ON corrections(correction_type);
CREATE INDEX IF NOT EXISTS idx_corrections_applied ON corrections(is_applied);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = """
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    language VARCHAR(50) NOT NULL DEFAULT '',
    framework VARCHAR(100) NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_scanned_at TIMESTAMPTZ,
    file_count INTEGER NOT NULL DEFAULT 0,
    total_chunks INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);
CREATE INDEX IF NOT EXISTS idx_projects_root ON projects(root_path);

CREATE TABLE IF NOT EXISTS project_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL DEFAULT '',
    language VARCHAR(50) NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    last_modified TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_indexed BOOLEAN NOT NULL DEFAULT false,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_pfiles_project ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_pfiles_hash ON project_files(file_hash);

CREATE TABLE IF NOT EXISTS project_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES project_files(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '',
    start_line INTEGER NOT NULL DEFAULT 0,
    end_line INTEGER NOT NULL DEFAULT 0,
    symbol_name VARCHAR(255),
    symbol_type VARCHAR(50),
    embedding BYTEA,
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pchunks_file ON project_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_pchunks_project ON project_chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_pchunks_symbol ON project_chunks(symbol_name);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    user_message TEXT NOT NULL DEFAULT '',
    assistant_response TEXT NOT NULL DEFAULT '',
    model_used VARCHAR(100) NOT NULL DEFAULT '',
    cache_hit BOOLEAN NOT NULL DEFAULT false,
    rating SMALLINT,
    feedback TEXT,
    context_used JSONB NOT NULL DEFAULT '[]',
    generation_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_rating ON conversations(rating);

CREATE TABLE IF NOT EXISTS conversation_embeddings (
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    embedding BYTEA NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    original_question TEXT NOT NULL DEFAULT '',
    original_answer TEXT NOT NULL DEFAULT '',
    corrected_answer TEXT NOT NULL DEFAULT '',
    correction_type VARCHAR(50) NOT NULL DEFAULT 'factual',
    is_applied BOOLEAN NOT NULL DEFAULT false,
    embedding BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_corrections_project ON corrections(project_id);
CREATE INDEX IF NOT EXISTS idx_corrections_type ON corrections(correction_type);
CREATE INDEX IF NOT EXISTS idx_corrections_applied ON corrections(is_applied);
"""

# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------

SQL_MYSQL = """
CREATE TABLE IF NOT EXISTS projects (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    root_path TEXT NOT NULL,
    description TEXT NOT NULL,
    language VARCHAR(50) NOT NULL DEFAULT '',
    framework VARCHAR(100) NOT NULL DEFAULT '',
    is_active TINYINT NOT NULL DEFAULT 1,
    last_scanned_at TIMESTAMP NULL,
    file_count INT NOT NULL DEFAULT 0,
    total_chunks INT NOT NULL DEFAULT 0,
    metadata JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_projects_root (root_path(500))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS project_files (
    id CHAR(36) PRIMARY KEY,
    project_id CHAR(36) NOT NULL,
    relative_path TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL DEFAULT '',
    language VARCHAR(50) NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    last_modified TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_indexed TINYINT NOT NULL DEFAULT 0,
    chunk_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_pfiles_path (project_id, relative_path(400)),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS project_chunks (
    id CHAR(36) PRIMARY KEY,
    file_id CHAR(36) NOT NULL,
    project_id CHAR(36) NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    start_line INT NOT NULL DEFAULT 0,
    end_line INT NOT NULL DEFAULT 0,
    symbol_name VARCHAR(255),
    symbol_type VARCHAR(50),
    embedding BLOB,
    token_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES project_files(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversations (
    id CHAR(36) PRIMARY KEY,
    project_id CHAR(36),
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    model_used VARCHAR(100) NOT NULL DEFAULT '',
    cache_hit TINYINT NOT NULL DEFAULT 0,
    rating TINYINT,
    feedback TEXT,
    context_used JSON NOT NULL,
    generation_ms INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversation_embeddings (
    conversation_id CHAR(36) PRIMARY KEY,
    embedding BLOB NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS corrections (
    id CHAR(36) PRIMARY KEY,
    conversation_id CHAR(36),
    project_id CHAR(36),
    original_question TEXT NOT NULL,
    original_answer TEXT NOT NULL,
    corrected_answer TEXT NOT NULL,
    correction_type VARCHAR(50) NOT NULL DEFAULT 'factual',
    is_applied TINYINT NOT NULL DEFAULT 0,
    embedding BLOB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def apply_mongodb(db):
    """Create project knowledge collections with indexes."""
    for name in ("projects", "project_files", "project_chunks", "conversations", "conversation_embeddings", "corrections"):
        if name not in db.list_collection_names():
            db.create_collection(name)

    db["projects"].create_index("root_path", unique=True)
    db["projects"].create_index("is_active")

    db["project_files"].create_index([("project_id", 1), ("relative_path", 1)], unique=True)
    db["project_files"].create_index("file_hash")

    db["project_chunks"].create_index("file_id")
    db["project_chunks"].create_index("project_id")
    db["project_chunks"].create_index("symbol_name")

    db["conversations"].create_index("project_id")
    db["conversations"].create_index("created_at")

    db["corrections"].create_index("project_id")
    db["corrections"].create_index("correction_type")
