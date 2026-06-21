# ADR-002: SQLite as Default Database Backend

## Status

Accepted

## Context

BitMod's core value proposition is "pip install and see the savings." The first-run experience must require zero external infrastructure. If a user has to install and configure PostgreSQL before they can observe cache hit rates and cost reduction, adoption friction kills the product.

At the same time, production deployments serving multiple application instances need a database that supports concurrent writes from separate processes and can scale beyond a single node.

We need a default that works out of the box for evaluation and single-instance use, with a clear upgrade path for production.

## Decision

SQLite is the default database backend. PostgreSQL is the recommended backend for production and multi-instance deployments.

Implementation details:

- The SQLite adapter (`core/bitmod/adapters/db_sqlite.py`) uses WAL (Write-Ahead Logging) mode by default, which allows concurrent reads while a write is in progress.
- The database file is created automatically at `~/.bitmod/bitmod.db` on first use. No configuration required.
- Schema migrations are embedded in the adapter and run on startup, so the database is always at the current schema version.
- Switching to PostgreSQL requires only setting `BITMOD_DB_URL` to a PostgreSQL connection string. The adapter is selected automatically based on the URL scheme.
- Both adapters implement the same `DatabaseBackend` ABC (see ADR-001), so the cache engine and all other core logic are backend-agnostic.

## Consequences

**What becomes easier:**

- First-run experience is truly zero-config. `pip install bitmod && bitmod serve` works immediately with no database setup.
- Local development and testing require no Docker containers or external services.
- The SQLite file is portable and inspectable. Users can query their cache statistics directly with any SQLite client.
- CI tests run fast against SQLite without needing a database service container.

**What becomes harder or requires care:**

- SQLite does not support concurrent writes from multiple processes. Multi-instance deployments (e.g., multiple gateway replicas behind a load balancer) must migrate to PostgreSQL.
- WAL mode improves concurrent read performance but does not eliminate the single-writer limitation. Under heavy write load from a single process, write contention is minimal, but it is still a single-process ceiling.
- Schema differences between SQLite and PostgreSQL must be tested. The CI matrix runs tests against both backends to catch dialect-specific issues (e.g., SQLite lacks native JSON operators, array types, and some ALTER TABLE operations).
- Documentation must clearly communicate when to switch to PostgreSQL: as soon as the deployment involves more than one BitMod instance or expects sustained high write throughput.
