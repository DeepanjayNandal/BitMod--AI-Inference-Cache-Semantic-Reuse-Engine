# Contributing to BitMod

Thank you for your interest in contributing to BitMod! This guide will help you get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/BitModerator/bitmod.git
cd bitmod

# Install in development mode
pip install -e ".[dev,server]"

# Run tests
pytest

# Run linter
ruff check core/ services/
```

## Project Structure

```
bitmod/
├── core/bitmod/          # Core library (pip-installable)
│   ├── adapters/         # Provider adapters (LLM, DB, embeddings)
│   ├── interfaces/       # Abstract base classes
│   └── ingestion/        # Document parsing + chunking
├── services/
│   ├── gateway/          # API gateway (FastAPI)
│   ├── chat/             # Chat service (FastAPI)
│   └── frontend/         # Dashboard (Next.js)
└── docker-compose.yml
```

## How to Contribute

### Reporting Bugs

Open an issue on GitHub with:
- A clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, database backend)

### Suggesting Features

Open a GitHub Discussion or Issue describing:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest`
5. Run linter: `ruff check core/ services/`
6. Commit with a clear message
7. Push and open a Pull Request

### Adding a New Adapter

BitMod's adapter system makes it easy to add new providers:

**LLM Provider:**
1. Create `core/bitmod/adapters/llm_yourprovider.py`
2. Implement the `LLMProvider` interface from `core/bitmod/interfaces/llm.py`
3. Register in `core/bitmod/adapters/__init__.py`
4. Add optional dependency group in `pyproject.toml`

**Database Backend:**
1. Create `core/bitmod/adapters/db_yourdb.py`
2. Implement the `DatabaseBackend` interface from `core/bitmod/interfaces/database.py`
3. Register in `core/bitmod/adapters/__init__.py`

**Embedding Provider:**
1. Create `core/bitmod/adapters/embed_yourprovider.py`
2. Implement the `EmbeddingProvider` interface from `core/bitmod/interfaces/embeddings.py`
3. Register in `core/bitmod/adapters/__init__.py`

### Code Style

- Python: Follow PEP 8, enforced by `ruff`
- Target Python 3.10+ compatibility
- Type hints encouraged but not required
- Keep dependencies minimal — core should work with just `pydantic`, `httpx`, `PyYAML`

### Commit Messages

- Use present tense: "Add feature" not "Added feature"
- Keep the first line under 72 characters
- Reference issues when applicable: "Fix #123: handle empty query"

## Architecture Decision Records (ADRs)

Significant architectural decisions are documented in `docs/adr/` using [Michael Nygard's ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions). Each ADR captures the context, decision, and consequences of a design choice.

To propose a new ADR:

1. Copy the template: use the format from any existing ADR in `docs/adr/`
2. Number sequentially: `NNN-short-title.md` (e.g., `004-caching-strategy.md`)
3. Set status to `Proposed` and submit with your pull request
4. Status moves to `Accepted` once merged, or `Deprecated` if superseded

## Known Test Gaps

The following modules have limited or no dedicated test coverage yet:

- **`core/bitmod/api.py`** — REST API layer needs integration tests covering error paths, auth flows, and streaming responses.
- **`core/bitmod/cli.py`** — CLI commands need end-to-end tests (doctor, query offline fallback, init, migrate, backup). Currently only tested indirectly via integration tests.
- **`sdk/python/`** — Async SDK client needs tests covering streaming, retry logic, and error handling.

Contributions adding tests for any of these are welcome.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
