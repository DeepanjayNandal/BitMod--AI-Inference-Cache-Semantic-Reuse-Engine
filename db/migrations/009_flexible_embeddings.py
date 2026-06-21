"""Migration 009: Resize embedding columns to match configured dimensions.

Reads BITMOD_EMBEDDING_DIMENSIONS (default 384) and ALTERs the PostgreSQL
vector columns to the correct size.  SQLite stores embeddings as BLOB so
dimension is implicit — no change needed.  MySQL uses BLOB/LONGBLOB
similarly.

Idempotent: PostgreSQL ALTER TYPE ... USING re-casts in place.
"""

from __future__ import annotations

import os

VERSION = 9
NAME = "flexible_embeddings"

_DIM = int(os.getenv("BITMOD_EMBEDDING_DIMENSIONS", "384"))

# ---------------------------------------------------------------------------
# SQLite — embedding is BLOB, dimension is implicit. Nothing to do.
# ---------------------------------------------------------------------------

SQL_SQLITE = ""

# ---------------------------------------------------------------------------
# PostgreSQL — ALTER the vector(N) columns to the configured dimension.
# Uses ALTER COLUMN ... TYPE which is idempotent (no-op if already correct).
# ---------------------------------------------------------------------------

SQL_POSTGRESQL = f"""
ALTER TABLE chunks
    ALTER COLUMN embedding TYPE vector({_DIM})
    USING embedding::vector({_DIM});

ALTER TABLE cache_embeddings
    ALTER COLUMN embedding TYPE vector({_DIM})
    USING embedding::vector({_DIM});
"""

# ---------------------------------------------------------------------------
# MySQL — embedding is LONGBLOB, dimension is implicit. Nothing to do.
# ---------------------------------------------------------------------------

SQL_MYSQL = ""
