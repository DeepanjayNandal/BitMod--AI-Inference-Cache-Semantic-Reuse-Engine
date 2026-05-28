"""Lightweight database migration runner — zero external dependencies.

Tracks schema versions in a `schema_migrations` table and applies
incremental migrations across all supported backends (SQLite, PostgreSQL,
MySQL, MongoDB).

Usage:
    from bitmod.migrations import MigrationRunner
    runner = MigrationRunner(backend)
    with backend.session() as session:
        runner.migrate(session)
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import pkgutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bitmod.interfaces.database import DatabaseBackend

logger = logging.getLogger("bitmod.migrations")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Migration:
    """A single migration loaded from a Python module."""

    version: int
    name: str
    checksum: str  # SHA-256 of the SQL/operation content
    # Backend-specific SQL strings
    sql_sqlite: str = ""
    sql_postgresql: str = ""
    sql_mysql: str = ""
    # MongoDB uses a callable instead of SQL
    apply_mongodb: Any = None  # Callable[[db], None] or None
    # Source module path for diagnostics
    module_path: str = ""


@dataclass
class AppliedMigration:
    """Record of a migration that has already been applied."""

    id: int
    version: int
    name: str
    applied_at: str
    checksum: str


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------


def _detect_backend_type(backend: DatabaseBackend) -> str:
    """Determine the backend type from the class name / module path."""
    cls_name = type(backend).__name__.lower()
    module = type(backend).__module__.lower()
    combined = f"{module}.{cls_name}"

    if "sqlite" in combined:
        return "sqlite"
    if "postgres" in combined or "pg" in combined:
        return "postgresql"
    if "mysql" in combined or "maria" in combined:
        return "mysql"
    if "mongo" in combined:
        return "mongodb"

    # Fallback: check for known attributes
    if hasattr(backend, "_path") and str(getattr(backend, "_path", "")).endswith(".db"):
        return "sqlite"

    return "sqlite"  # safe default


# ---------------------------------------------------------------------------
# SQL for the schema_migrations tracking table
# ---------------------------------------------------------------------------

_CREATE_MIGRATIONS_TABLE = {
    "sqlite": """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            checksum TEXT NOT NULL
        );
    """,
    "postgresql": """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            version INTEGER NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            checksum VARCHAR(64) NOT NULL
        );
    """,
    "mysql": """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            version INT NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            checksum VARCHAR(64) NOT NULL
        );
    """,
}


# ---------------------------------------------------------------------------
# Migration discovery
# ---------------------------------------------------------------------------


def _compute_checksum(migration_module: Any, backend_type: str) -> str:
    """SHA-256 checksum of the migration content for a given backend."""
    if backend_type == "mongodb":
        # Hash the source of the apply_mongodb function if present
        import inspect

        fn = getattr(migration_module, "apply_mongodb", None)
        content = inspect.getsource(fn) if fn else ""
    else:
        attr = f"SQL_{backend_type.upper()}"
        content = getattr(migration_module, attr, "")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def discover_migrations(migrations_path: str | Path | None = None) -> list[Migration]:
    """Discover migration modules from the db/migrations package.

    Migration modules must define at minimum:
        VERSION: int
        NAME: str
    And one or more of:
        SQL_SQLITE: str
        SQL_POSTGRESQL: str
        SQL_MYSQL: str
        def apply_mongodb(db): ...
    """
    if migrations_path is None:
        # Default: look for db.migrations package
        try:
            import db.migrations as pkg

            pkg_path = Path(pkg.__file__).parent if pkg.__file__ else None
        except ImportError:
            # Fallback: relative to this file
            pkg_path = Path(__file__).resolve().parent.parent.parent / "db" / "migrations"
            if not pkg_path.is_dir():
                return []
    else:
        pkg_path = Path(migrations_path)

    if pkg_path is None or not pkg_path.is_dir():
        return []

    migrations: list[Migration] = []

    # Scan for Python modules matching NNN_*.py pattern
    import sys

    # Ensure the parent of db/ is on sys.path so `db.migrations` can be imported
    project_root = pkg_path.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    for finder, module_name, is_pkg in pkgutil.iter_modules([str(pkg_path)]):
        if is_pkg or not module_name[0].isdigit():
            continue

        try:
            spec = importlib.util.spec_from_file_location(  # type: ignore[attr-defined]
                f"db.migrations.{module_name}",
                str(pkg_path / f"{module_name}.py"),
            )
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)  # type: ignore[attr-defined]
            spec.loader.exec_module(mod)
        except Exception as exc:
            logger.warning("Failed to load migration %s: %s", module_name, exc)
            continue

        version = getattr(mod, "VERSION", None)
        name = getattr(mod, "NAME", None)
        if version is None or name is None:
            logger.warning("Migration %s missing VERSION or NAME, skipping", module_name)
            continue

        # Build a combined checksum from all backend SQL
        all_content = "".join(
            [
                getattr(mod, "SQL_SQLITE", ""),
                getattr(mod, "SQL_POSTGRESQL", ""),
                getattr(mod, "SQL_MYSQL", ""),
            ]
        )
        import inspect

        fn = getattr(mod, "apply_mongodb", None)
        if fn:
            all_content += inspect.getsource(fn)
        checksum = hashlib.sha256(all_content.encode("utf-8")).hexdigest()

        migrations.append(
            Migration(
                version=version,
                name=name,
                checksum=checksum,
                sql_sqlite=getattr(mod, "SQL_SQLITE", ""),
                sql_postgresql=getattr(mod, "SQL_POSTGRESQL", ""),
                sql_mysql=getattr(mod, "SQL_MYSQL", ""),
                apply_mongodb=fn,
                module_path=str(pkg_path / f"{module_name}.py"),
            )
        )

    migrations.sort(key=lambda m: m.version)
    return migrations


# ---------------------------------------------------------------------------
# SQL statement splitting (for graceful ALTER TABLE handling)
# ---------------------------------------------------------------------------


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements on semicolons.

    Respects quoted strings and $$ blocks (PostgreSQL functions).
    Returns a list of non-empty statements.
    """
    statements: list[str] = []
    current: list[str] = []
    in_dollar = False

    for line in sql.split("\n"):
        stripped = line.strip()

        # Track $$ blocks
        if "$$" in stripped:
            in_dollar = not in_dollar

        if not in_dollar and ";" in line:
            # Split on semicolons outside $$ blocks
            parts = line.split(";")
            for i, part in enumerate(parts):
                current.append(part)
                if i < len(parts) - 1:
                    stmt = "\n".join(current).strip()
                    if stmt:
                        statements.append(stmt)
                    current = []
        else:
            current.append(line)

    # Remaining content
    remainder = "\n".join(current).strip()
    if remainder:
        statements.append(remainder)

    return statements


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


class MigrationRunner:
    """Tracks and applies database schema migrations."""

    def __init__(self, backend: DatabaseBackend, migrations_path: str | Path | None = None):
        self._backend = backend
        self._backend_type = _detect_backend_type(backend)
        self._migrations_path = migrations_path
        self._all_migrations: list[Migration] | None = None

    @property
    def backend_type(self) -> str:
        return self._backend_type

    def _get_migrations(self) -> list[Migration]:
        if self._all_migrations is None:
            self._all_migrations = discover_migrations(self._migrations_path)
        return self._all_migrations

    # --- Schema migrations table ---

    def ensure_migration_table(self, session: Any) -> None:
        """Create the schema_migrations table if it does not exist."""
        if self._backend_type == "mongodb":
            # MongoDB: nothing to create, we use a collection
            return

        sql = _CREATE_MIGRATIONS_TABLE.get(self._backend_type)
        if sql is None:
            raise ValueError(f"Unsupported backend type: {self._backend_type}")

        if self._backend_type == "sqlite":
            session.executescript(sql)
        else:
            session.execute(sql)

    # --- Version tracking ---

    def get_applied(self, session: Any) -> list[AppliedMigration]:
        """Return all applied migrations ordered by version."""
        if self._backend_type == "mongodb":
            collection = session["schema_migrations"]
            docs = list(collection.find().sort("version", 1))
            return [
                AppliedMigration(
                    id=i,
                    version=doc["version"],
                    name=doc["name"],
                    applied_at=str(doc.get("applied_at", "")),
                    checksum=doc.get("checksum", ""),
                )
                for i, doc in enumerate(docs, 1)
            ]

        rows = session.execute(
            "SELECT id, version, name, applied_at, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()

        results = []
        for row in rows:
            if isinstance(row, dict):
                results.append(AppliedMigration(**row))
            elif hasattr(row, "keys"):
                # sqlite3.Row
                results.append(
                    AppliedMigration(
                        id=row["id"],
                        version=row["version"],
                        name=row["name"],
                        applied_at=str(row["applied_at"]),
                        checksum=row["checksum"],
                    )
                )
            else:
                results.append(
                    AppliedMigration(
                        id=row[0],
                        version=row[1],
                        name=row[2],
                        applied_at=str(row[3]),
                        checksum=row[4],
                    )
                )
        return results

    def get_current_version(self, session: Any) -> int:
        """Return the highest applied migration version, or 0 if none."""
        applied = self.get_applied(session)
        if not applied:
            return 0
        return max(m.version for m in applied)

    def get_pending(self, session: Any) -> list[Migration]:
        """Return migrations not yet applied, sorted by version."""
        applied_versions = {m.version for m in self.get_applied(session)}
        return [m for m in self._get_migrations() if m.version not in applied_versions]

    # --- Apply ---

    def apply(self, session: Any, migration: Migration) -> None:
        """Apply a single migration and record it in schema_migrations."""
        bt = self._backend_type

        if bt == "mongodb":
            if migration.apply_mongodb:
                migration.apply_mongodb(session)
            else:
                logger.warning(
                    "Migration %03d (%s) has no apply_mongodb function, skipping",
                    migration.version,
                    migration.name,
                )
                return
            # Record it
            session["schema_migrations"].insert_one(
                {
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": datetime.now(timezone.utc),
                    "checksum": migration.checksum,
                }
            )
            return

        # SQL backends
        sql_attr = f"sql_{bt}"
        sql = getattr(migration, sql_attr, "")
        if not sql:
            logger.warning(
                "Migration %03d (%s) has no SQL for %s, skipping",
                migration.version,
                migration.name,
                bt,
            )
            return

        # Execute the migration SQL
        if bt == "sqlite":
            # Execute each statement individually so ALTER TABLE errors
            # (e.g., "duplicate column") don't abort the whole migration.
            for stmt in _split_sql_statements(sql):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    session.execute(stmt)
                except Exception as exc:
                    # Gracefully handle expected ALTER TABLE errors
                    err_msg = str(exc).lower()
                    if "duplicate column" in err_msg or "already exists" in err_msg:
                        logger.debug(
                            "Skipping already-applied statement: %s",
                            exc,
                        )
                    else:
                        raise
        else:
            # PostgreSQL / MySQL: execute statements
            # Split on semicolons but respect $$ blocks (PG functions)
            session.execute(sql)

        # Record the migration
        if bt == "sqlite":
            session.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (?, ?, ?)",
                (migration.version, migration.name, migration.checksum),
            )
        else:
            session.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )

    def migrate(self, session: Any, target_version: int | None = None) -> list[Migration]:
        """Apply all pending migrations up to target_version.

        Returns the list of migrations that were applied.
        """
        self.ensure_migration_table(session)
        pending = self.get_pending(session)

        if target_version is not None:
            pending = [m for m in pending if m.version <= target_version]

        applied: list[Migration] = []
        for migration in pending:
            logger.info(
                "Applying migration %03d: %s",
                migration.version,
                migration.name,
            )
            t0 = time.monotonic()
            self.apply(session, migration)
            elapsed = time.monotonic() - t0
            logger.info(
                "Migration %03d applied in %.2fs",
                migration.version,
                elapsed,
            )
            applied.append(migration)

        return applied

    def status(self, session: Any) -> dict:
        """Return migration status: current version, pending count, full history."""
        self.ensure_migration_table(session)

        applied = self.get_applied(session)
        pending = self.get_pending(session)
        current = max((m.version for m in applied), default=0)

        return {
            "backend": self._backend_type,
            "current_version": current,
            "pending_count": len(pending),
            "applied_count": len(applied),
            "pending": [{"version": m.version, "name": m.name} for m in pending],
            "history": [
                {
                    "version": m.version,
                    "name": m.name,
                    "applied_at": m.applied_at,
                    "checksum": m.checksum[:12] + "...",
                }
                for m in applied
            ],
        }

    def verify_checksums(self, session: Any) -> list[dict]:
        """Check for checksum mismatches between applied and on-disk migrations.

        Returns a list of mismatches (empty = all good).
        """
        self.ensure_migration_table(session)
        applied = {m.version: m for m in self.get_applied(session)}
        all_migs = {m.version: m for m in self._get_migrations()}

        mismatches = []
        for version, applied_mig in applied.items():
            disk_mig = all_migs.get(version)
            if disk_mig is None:
                mismatches.append(
                    {
                        "version": version,
                        "name": applied_mig.name,
                        "issue": "migration file missing from disk",
                    }
                )
            elif disk_mig.checksum != applied_mig.checksum:
                mismatches.append(
                    {
                        "version": version,
                        "name": applied_mig.name,
                        "issue": "checksum mismatch (migration modified after apply)",
                        "applied_checksum": applied_mig.checksum[:12],
                        "disk_checksum": disk_mig.checksum[:12],
                    }
                )
        return mismatches
