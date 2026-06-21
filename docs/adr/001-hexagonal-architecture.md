# ADR-001: Hexagonal (Ports-and-Adapters) Architecture

## Status

Accepted

## Context

BitMod is designed to integrate with a wide range of external systems: 12 LLM providers (OpenAI, Anthropic, Google, Mistral, Cohere, etc.), 4 database backends (SQLite, PostgreSQL, MySQL, MongoDB), multiple embedding providers, and various messaging/vector store systems. Each provider has its own SDK, authentication model, and API surface.

Without a clear boundary between business logic and external integrations, the codebase would accumulate provider-specific conditionals throughout the cache engine and request pipeline. Adding a new provider would require modifying core logic, increasing regression risk and making the system harder to test.

## Decision

We adopt hexagonal architecture (ports-and-adapters) as the primary structural pattern for BitMod's core library.

- **Ports** are defined as Python abstract base classes (ABCs) in `core/bitmod/interfaces/`. Each port defines the contract that any adapter must satisfy: `LLMProvider`, `DatabaseBackend`, `EmbeddingProvider`, `VectorStore`, `MessagingBackend`.
- **Adapters** live in `core/bitmod/adapters/` and implement exactly one port. Each adapter file is named by convention: `llm_openai.py`, `db_sqlite.py`, `embed_sentence_transformers.py`, etc.
- **Core logic** (the cache engine, intent router, ingestion pipeline) depends only on the port interfaces, never on concrete adapters.
- Adapter selection happens at startup via configuration, using a simple registry pattern in `core/bitmod/adapters/__init__.py`.

## Consequences

**What becomes easier:**

- Adding a new LLM provider or database backend requires only a single new adapter file that implements the existing ABC. No changes to core logic.
- Unit testing the cache engine and pipeline is straightforward: inject a mock that satisfies the interface contract. No need to spin up real databases or call real APIs.
- Provider-specific bugs are isolated to their adapter. A regression in the Anthropic adapter cannot affect the OpenAI code path.
- The architecture is self-documenting: reading the interface files tells you exactly what any adapter must do.

**What becomes harder or requires care:**

- There is a thin abstraction overhead. Every external call goes through an interface method rather than calling the SDK directly. This adds a small amount of indirection but no measurable performance cost.
- Interface design must be done carefully. If an ABC is too narrow, adapters need workarounds. If too broad, some adapters cannot fully implement the contract. We mitigate this by keeping interfaces minimal and using optional capability flags where providers diverge (e.g., streaming support, function calling).
- Contributors must understand the pattern. The CONTRIBUTING.md documents the process for adding adapters, and the existing adapters serve as reference implementations.
