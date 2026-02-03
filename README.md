# Bitmod

[![CI](https://github.com/BitModerator/bitmod/actions/workflows/ci.yml/badge.svg)](https://github.com/BitModerator/bitmod/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Modular AI Data Infrastructure — Compute once, serve forever.**

Bitmod is an intelligent caching and retrieval engine for AI applications. It ingests your documents, embeds them for semantic search, and caches LLM-generated answers so identical or similar questions are served instantly — never recomputed.

**7-layer intelligent cache engine** | **200+ LLM providers** | **4 database backends** | **4 embedding providers** | **9 document formats** | **1000+ tests**

```
pip install bitmod
bitmod init
bitmod ingest ./docs/
bitmod query "What is our refund policy?"
```

## Quickstart

### Option A: pip install (simplest)

```bash
pip install bitmod

# Interactive setup — auto-detects your LLM, embeddings, and database
bitmod init

# Ingest documents
bitmod ingest ./my-documents/

# Query with intelligent caching
bitmod query "What are the key takeaways?"

# Start the API server
bitmod serve
```

### Option B: Docker (one command)

```bash
git clone https://github.com/BitModerator/bitmod.git
cd bitmod

# Interactive setup
bitmod init

# Start services
docker compose up
```

The default stack runs gateway + chat + frontend with SQLite. Add profiles for more:

```bash
# With local Ollama (no API keys needed)
docker compose --profile ollama up

# With PostgreSQL + pgvector (production)
docker compose --profile postgres up

# Everything
docker compose --profile ollama --profile postgres up
```

### Option C: Python library

```python
from bitmod import Bitmod

bm = Bitmod()
bm.ingest("./reports/")
result = bm.query("What was Q3 revenue?")

print(result.answer)       # The answer
print(result.cached)       # True if served from cache
print(result.sources)      # Source citations
print(result.generation_ms)  # 0ms if cached
```

## How It Works

```
Query → Normalize → Cache Pipeline (7 active layers) → Hit? → Serve
                                                      → Miss? → LLM (with cached context) → Cache → Serve
```

### Cache Engine

Bitmod uses a **probabilistic evidence accumulation** model — cache layers contribute graded confidence scores, composed multiplicatively (`1 - ∏(1 - cᵢ)`). Negative evidence (e.g. stale sources) is subtracted, and results are clamped to [0, 1].

The pipeline runs layers in order, serving immediately on a high-confidence hit:

1. **Query Normalization** — Lowercase, strip stopwords, composite SHA-256 key
2. **Exact Match** — O(1) cache lookup by composite key
3. **Double Verification** — Re-check source version hashes before serving (prevents stale data)
4. **Semantic Matching** — Embedding-based similarity search (0.92 threshold for direct serve, 0.75 for LLM context)
5. **Composable Decomposition** — "Compare X in CA vs TX" splits into cached sub-queries
6. **Fuzzy Matching** — Jaccard + overlap similarity for near-duplicate questions (0.80 threshold)
7. **Cascade Invalidation & Metrics** — Source changes invalidate dependent answers; TTL expiration; hit rate tracking

Planned but not yet wired into the live pipeline:

8. **Similarity Link Traversal** — Walk a learned near-miss graph of related queries
9. **Atomic Fact Search** — Reusable facts decomposed from prior answers

### Cache Qualification Layer

Before serving a cached answer, Bitmod runs a qualification gate that detects context-dependent queries — anaphoric references ("tell me more"), continuations ("what's next"), and pronoun-heavy follow-ups ("how does it work"). These are skipped from cache and sent to the LLM with full conversation context, preventing stale or misleading cached responses in multi-turn conversations.

### Post-Generation Intelligence

After every LLM call, the system:
- **Caches the answer** with composite SHA-256 key, source version hashes, and query embedding
- **Stores the query embedding** alongside the cached answer for future semantic matching
- **Tracks cache metrics** — hit rates, serve counts, generation times, token savings

### Block-Level Caching

Each document section is stored at three compression levels:
- **Full** — Complete text with token count
- **Headline** — Title or first sentence (for quick scanning)
- **Structured** — Extracted entities, dates, amounts, key-value pairs (JSON)

## Configuration

### Universal LLM Config (simplest)

Just 3 environment variables work with any OpenAI-compatible provider:

```bash
export BITMOD_LLM_URL=https://api.groq.com/openai/v1   # or any provider
export BITMOD_LLM_API_KEY=your-key
export BITMOD_LLM_MODEL=llama-3.3-70b
```

This works with Ollama, OpenAI, Groq, Together, Fireworks, vLLM, LM Studio, Jan.ai, and 200+ more providers that support the OpenAI-compatible API format.

### YAML Config

`bitmod init` creates a `bitmod.yaml` with interactive prompts:

```yaml
# bitmod.yaml
llm_url: http://localhost:11434/v1    # Ollama default
llm_model: llama3.2

embedding_provider: ollama
embedding_model: nomic-embed-text

db_backend: sqlite                     # or: postgresql, mysql, mongodb
```

### Provider-Specific Config

For providers with native adapters (richer features like tool calling):

```bash
export BITMOD_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-...
```

Environment variables always take precedence over YAML. See [`.env.example`](.env.example) for all options.

## Supported Providers

### LLM (200+ via universal adapter)

Any provider with an OpenAI-compatible API works out of the box. Native adapters with full feature support:

| Provider | Key | Models |
|----------|-----|--------|
| **Any OpenAI-compatible** | `BITMOD_LLM_API_KEY` | Groq, Together, Fireworks, vLLM, LM Studio, Jan.ai, 200+ more |
| Ollama | none | llama3.2, mistral, phi3, gemma2 |
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4, claude-haiku |
| OpenAI | `OPENAI_API_KEY` | gpt-4o, gpt-4o-mini |
| Gemini | `GEMINI_API_KEY` | gemini-2.0-flash |
| xAI | `XAI_API_KEY` | grok-3 |
| Mistral | `MISTRAL_API_KEY` | mistral-large |
| Perplexity | `PERPLEXITY_API_KEY` | sonar-pro |
| OpenRouter | `OPENROUTER_API_KEY` | any model via unified gateway |
| HuggingFace | `HF_API_KEY` | inference API models |
| AWS Bedrock | IAM credentials | Claude, Titan, Llama |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` | GPT-4o via Azure |

### Embeddings (4 providers)

| Provider | Model | Dimensions |
|----------|-------|------------|
| Ollama | nomic-embed-text | 768 |
| Local | all-MiniLM-L6-v2 | 384 |
| OpenAI | text-embedding-3-small | 1536 |
| Cohere | embed-v4.0 | 1024 |

### Databases (4 backends)

| Backend | Search | Best For |
|---------|--------|----------|
| SQLite | FTS5 + cosine similarity | Development, single-node |
| PostgreSQL | BM25 + pgvector | Production |
| MySQL | FULLTEXT + approximate | MySQL shops |
| MongoDB | Atlas Search | Document-heavy workloads |

### Vector Stores (3 providers)

| Provider | Best For |
|----------|----------|
| Chroma | Local development, prototyping |
| Qdrant | Production vector search |
| Pinecone | Managed cloud vector DB |

### Messaging (5 channels)

| Channel | Adapter |
|---------|---------|
| Slack | Workspace integration |
| Discord | Bot integration |
| Telegram | Bot API |
| Matrix | Federated messaging |
| WhatsApp | Business API |

### Document Formats (9)

PDF, DOCX, HTML, Markdown, CSV, JSON, Plain Text, RST, Log files

## API

### Ingest

```bash
# Text
curl -X POST http://localhost:8000/v1/ingest/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Your content here...", "title": "My Doc"}'

# File upload
curl -X POST http://localhost:8000/v1/ingest/file \
  -F "file=@report.pdf" \
  -F "title=Q3 Report"
```

### Chat

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the key findings?", "stream": false}'
```

### Search

```bash
curl -X POST http://localhost:8000/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "revenue growth", "limit": 10}'
```

### Status

```bash
curl http://localhost:8000/v1/ingest/status   # Documents
curl http://localhost:8000/v1/cache/stats      # Cache performance
curl http://localhost:8000/v1/admin/metrics    # Full dashboard data
```

## CLI

```
bitmod init                       Interactive setup
bitmod init --auto                Zero-config setup (Ollama + SQLite)
bitmod ingest <path>              Ingest file or directory
bitmod ingest -                   Ingest from stdin (piping)
bitmod query "question"           Query with cache stats
bitmod serve                      Start API server
bitmod proxy                      Start reverse proxy
bitmod status                     System status
bitmod doctor                     Health check all dependencies
bitmod cache stats                Cache hit rates and performance
bitmod cache recent               Recently cached queries
bitmod cache search "term"        Fuzzy search the cache
bitmod backup list                List backup sessions
bitmod backup create              Create a backup
bitmod migrate                    Run database migrations
bitmod update                     Check for updates
bitmod config show                Show current configuration
bitmod completions bash|zsh|fish  Shell completion scripts
```

### Global Flags

```
--format json    Structured JSON output (all commands)
--format text    Human-readable output (default)
-q, --quiet      Suppress non-essential output
--version        Show version
```

### Piping & Scripting

```bash
# Pipe content directly
cat document.txt | bitmod ingest -

# JSON output for scripting
bitmod --format json status | jq '.cache_stats.hit_rate'
bitmod --format json doctor | jq '.healthy'

# Shell completions (auto-install)
bitmod completions bash --install
bitmod completions zsh --install
bitmod completions fish --install
```

## Benchmark Results

Real-world benchmarks with Ollama (llama3.2) on a multi-pass test suite:

| Metric | Result |
|--------|--------|
| **Cache hit rate** | 50.7% (across all active layers) |
| **Token savings** | 69.1% reduction in LLM calls |
| **Exact match** | 100% hit rate on repeated queries |
| **Semantic match** | Catches rephrased questions automatically |
| **Latency** | 0ms for cached responses vs 500ms+ for LLM |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Frontend                              │
│                   (Next.js Admin + Chat)                      │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                        Gateway                                │
│    Rate Limiting · CORS · Auth (JWT/RBAC) · Security Headers  │
│    Ingest API · Cache Stats · Metrics · Namespaces            │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                      Chat Service                             │
│   7-Layer Cache · Evidence Accumulation · Cache Qualification │
│   Tool Calling · Streaming · Intent Detection · Sessions      │
└───┬──────────┬──────────┬──────────┬──────────┬──────────────┘
    │          │          │          │          │
┌───▼───┐ ┌───▼────┐ ┌───▼───┐ ┌───▼────┐ ┌───▼──────┐
│  LLM  │ │Embedder│ │  DB   │ │ Vector │ │ Messaging│
│ 200+  │ │4 provs │ │4 backs│ │3 stores│ │ 5 chans  │
└───────┘ └────────┘ └───────┘ └────────┘ └──────────┘
                        │
              ┌─────────▼─────────┐
              │   Reverse Proxy   │
              │ OpenAI · Anthropic│
              │ Gemini format     │
              └───────────────────┘
```

## Project Structure

```
bitmod/
├── core/bitmod/              # Core library (pip-installable)
│   ├── api.py                # Bitmod() class — ingest, query, status
│   ├── cache_engine.py       # 7-layer cache with evidence accumulation
│   ├── cache_qualify.py      # Cache qualification gate
│   ├── cli.py                # CLI (JSON output, completions, piping)
│   ├── config.py             # Configuration loader (YAML + env)
│   ├── blocks.py             # 3-compression block generation
│   ├── tags.py               # Auto-tagger (rule-based, zero LLM cost)
│   ├── tool_layer.py         # LLM function calling tools
│   ├── intent.py             # Intent detection engine
│   ├── intents/              # 15 intent templates (YAML)
│   ├── auth.py               # JWT authentication
│   ├── roles.py              # RBAC role management
│   ├── security.py           # Security middleware
│   ├── crypto.py             # Encryption utilities
│   ├── middleware.py          # Request/response middleware
│   ├── namespaces.py         # Multi-tenant namespace isolation
│   ├── session.py            # Conversation session management
│   ├── backup.py             # Backup/restore engine
│   ├── migrations.py         # Schema migration runner
│   ├── invalidation.py       # Cascade cache invalidation
│   ├── vector_index.py       # Vector similarity index
│   ├── messaging_bridge.py   # Multi-channel messaging bridge
│   ├── metrics.py            # Usage and performance metrics
│   ├── observability.py      # Logging and tracing
│   ├── pricing.py            # Cost tracking and billing
│   ├── usage.py              # Token and request usage tracking
│   ├── audit.py              # Audit logging
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── router.py             # Request routing
│   ├── output_filter.py      # Response filtering
│   ├── setup.py              # First-run setup wizard
│   ├── proxy/                # Reverse proxy (OpenAI/Anthropic/Gemini format)
│   ├── project/              # Project knowledge (indexer, memory, watcher)
│   ├── ingestion/            # Document parser + chunker + pipeline
│   ├── adapters/             # 28 provider adapters (LLM, DB, embed, vector, msg)
│   └── interfaces/           # Abstract base classes (LLM, DB, embed, vector, msg)
├── services/
│   ├── gateway/              # API gateway (FastAPI)
│   ├── chat/                 # Chat service (FastAPI + SSE streaming)
│   └── frontend/             # Admin dashboard (Next.js 15, React 19, Tailwind v4)
├── sdk/python/               # Python SDK (bitmod-client)
├── db/migrations/            # Database migration scripts
├── deploy/                   # Helm charts, docker-compose, monitoring
├── docs/                     # Architecture docs, ADRs, runbooks
├── tests/                    # 1000+ test functions
├── docker-compose.yml        # One-command setup
├── bitmod.yaml               # Configuration
└── pyproject.toml            # Package definition
```

## License

Apache 2.0
