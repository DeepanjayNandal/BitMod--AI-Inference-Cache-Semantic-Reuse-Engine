"""Migration 008: Add audit_events table.

Stores security and operational audit events for compliance and
forensic analysis.  Both SQLite and PostgreSQL schemas are idempotent.
"""

VERSION = 8
NAME = "audit_events"

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS audit_events (
    id             TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    actor          TEXT,
    source_ip      TEXT,
    resource       TEXT,
    action         TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    details_json   TEXT,
    correlation_id TEXT
);

CREATE INDEX IF NOT EXISTS ix_audit_events_timestamp  ON audit_events (timestamp);
CREATE INDEX IF NOT EXISTS ix_audit_events_event_type ON audit_events (event_type);
"""

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

SQL_POSTGRES = """
CREATE TABLE IF NOT EXISTS audit_events (
    id             TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    actor          TEXT,
    source_ip      TEXT,
    resource       TEXT,
    action         TEXT NOT NULL,
    outcome        TEXT NOT NULL,
    details_json   TEXT,
    correlation_id TEXT
);

CREATE INDEX IF NOT EXISTS ix_audit_events_timestamp  ON audit_events (timestamp);
CREATE INDEX IF NOT EXISTS ix_audit_events_event_type ON audit_events (event_type);
"""


def run_sqlite(conn) -> None:  # noqa: ANN001
    """Apply migration to a SQLite connection."""
    conn.executescript(SQL_SQLITE)


def run_postgres(conn) -> None:  # noqa: ANN001
    """Apply migration to a PostgreSQL connection."""
    conn.execute(SQL_POSTGRES)
