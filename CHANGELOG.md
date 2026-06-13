# Changelog

All notable changes to BitMod will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-29

### Added
- **9-layer intelligent cache engine** with probabilistic evidence accumulation
- **Cache qualification layer** — context-dependent query detection gates the cache pipeline
- **CLI maturity overhaul** — 17 commands, `--format json`, `--quiet`, stdin piping, shell completions (`--install` for bash/zsh/fish)
- Cache subcommands: `stats`, `recent`, `search`
- 12 native LLM adapters + universal OpenAI-compatible adapter supporting 200+ providers
- 4 database backends, 4 embedding providers, 3 vector stores, 5 messaging channels (28 provider adapters total)
- **Python SDK** (bitmod-client) with sync + async support
- **Frontend**: 25 pages including 5 new guide pages (API reference, Docker, operations, Python SDK, troubleshooting)
- Multi-pass benchmark pipeline: 50.7% hit rate, 69.1% token savings
- SQLite schema migrations: `last_served_at`, `namespace_id`, `max_age_seconds`, cohesive cache tables
- Security hardening: CVSS 9.1 fix, token validation, encryption at rest (AES-256-GCM), JWT RS256, token revocation, tenant-scoped rate limiting
- Security scanning in CI: gitleaks, pip-audit, semgrep (OWASP Top 10), npm audit
- Dependabot configuration, pre-commit hooks for secret scanning
- 9 Prometheus alerting rules + 16-panel Grafana dashboard
- Audit event logging, 5 incident response runbooks
- Helm production values and staging overrides
- Coverage threshold enforcement (60% minimum)
- CLAUDE.md project instructions

### Changed
- **Cache engine v2** — replaced winner-take-all pipeline with probabilistic evidence accumulation; all layers contribute graded confidence scores composed multiplicatively
- **Universal LLM config** — 3 env vars (`BITMOD_LLM_URL`, `BITMOD_LLM_API_KEY`, `BITMOD_LLM_MODEL`) replace 12 provider-specific configs; auto-detects provider from URL, defaults to Ollama at localhost:11434
- Playground upgraded with multi-turn sessions, provider selector, localStorage persistence

### Fixed
- Pre-release audit: 82 issues fixed (13 critical, 23 high, 29 medium, 17 low)
- All CI failures: 296 ruff lint errors, 102 mypy type errors → 0
- Frontend accuracy audit: removed ghost features, corrected adapter counts, fixed marketing claims
- Frontend ESLint migration from deprecated `next lint` to flat config
- Gateway→chat internal token and healthcheck issues
- README corrected against actual implementation (cache engine claims, adapter counts, architecture diagram)
- 972 tests passing, 0 lint errors, 0 mypy errors

## [0.1.0] - 2026-03-22

### Added
- Core library with 9-layer intelligent cache engine
- 12 native LLM provider adapters (Anthropic, OpenAI, Gemini, Ollama, xAI, Mistral, Perplexity, OpenRouter, HuggingFace, AWS Bedrock, Azure OpenAI, OpenAI-compatible)
- 4 database backends (SQLite, PostgreSQL, MySQL, MongoDB)
- 4 embedding providers (Ollama, local sentence-transformers, OpenAI, Cohere)
- 3 vector store integrations (ChromaDB, Qdrant, Pinecone)
- Document ingestion for 7 formats (PDF, DOCX, HTML, Markdown, CSV, JSON, plain text)
- OpenAI-compatible proxy endpoint for drop-in LLM replacement
- Block-level caching at three compression levels (full, headline, structured)
- Intent detection with role-based routing
- Cascade invalidation on content re-ingestion
- CLI (`bitmod init`, `bitmod ingest`, `bitmod query`, `bitmod serve`, `bitmod status`)
- API gateway with rate limiting, CORS, and security headers
- Database-backed API key management with JWT token exchange
- Chat service with streaming, tool calling, and source citations
- Next.js admin dashboard with playground
- Docker Compose deployment with profiles (default, ollama, postgres, full)
- Database migration system (9 migrations)
- Prometheus metrics and Redis caching support
- 5 messaging platform integrations (Slack, Discord, Telegram, WhatsApp, Matrix)
- Python SDK (bitmod-client) with sync + async support
- Helm charts for Kubernetes deployment
- 655+ test functions across 43 test files
