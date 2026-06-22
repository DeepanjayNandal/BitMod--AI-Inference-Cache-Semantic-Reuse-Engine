import type { Metadata } from "next"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { CodeBlock } from "@/components/shared/code-block"
import { ArrowRight, Clock, Book, Shield, Zap, Database } from "lucide-react"

export const metadata: Metadata = {
  title: "API Reference | Guides",
  description: "Complete REST API reference for BitMod: chat, search, ingestion, cache management, authentication, namespaces, and administration.",
}

export default function ApiReferenceGuide() {
  return (
    <div className="relative">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[120px]" />
      </div>

      <article className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-4">
            <Badge variant="accent">Reference</Badge>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span>20 min read</span>
            </div>
            <Badge className="bg-yellow-500/15 text-yellow-400 border-yellow-500/30">Intermediate</Badge>
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
            API Reference
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Complete REST API reference for BitMod. Every endpoint, request body, response format, and header — with curl and Python examples.
          </p>
        </div>

        <div className="space-y-16">
          {/* ------------------------------------------------------------------ */}
          {/* 1. Base URL & Authentication */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Base URL &amp; Authentication</h2>
            <p className="text-muted-foreground mb-4">
              All endpoints are served from the BitMod gateway. By default it listens on <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">http://localhost:8000</code>.
              In production, use your deployment URL.
            </p>

            <CodeBlock filename="terminal">
{`# Base URL
http://localhost:8000

# API key authentication (recommended)
curl -H "Authorization: Bearer bm_live_abc123..." \\
  http://localhost:8000/v1/chat/completions

# JWT authentication (for user-scoped access)
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \\
  http://localhost:8000/v1/chat/completions`}
            </CodeBlock>

            <p className="text-sm text-muted-foreground mt-4">
              All authenticated endpoints accept either an API key (prefixed <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">bm_</code>) or a JWT token in the <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">Authorization: Bearer</code> header.
              If authentication is disabled in your config, the header is optional.
            </p>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 2. Chat Completions (OpenAI-compatible) */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Chat Completions</h2>
            <p className="text-muted-foreground mb-4">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/chat/completions</code> — OpenAI-compatible chat endpoint. Drop-in replacement for any OpenAI SDK client.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Request</h3>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Explain semantic caching in one paragraph."}
    ],
    "temperature": 0.7,
    "max_tokens": 256,
    "stream": false
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "chatcmpl-bm-9f1a2b3c",
  "object": "chat.completion",
  "created": 1711540200,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Semantic caching stores LLM responses indexed by meaning rather than exact text..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 64,
    "total_tokens": 92
  }
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Streaming</h3>
            <p className="text-muted-foreground mb-4">
              Set <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">"stream": true</code> to receive Server-Sent Events. Each chunk follows the OpenAI streaming format:
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'

# Response (SSE):
# data: {"id":"chatcmpl-bm-9f1a2b3c","choices":[{"delta":{"content":"Hello"},"index":0}]}
# data: {"id":"chatcmpl-bm-9f1a2b3c","choices":[{"delta":{"content":"!"},"index":0}]}
# data: [DONE]`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Python SDK</h3>
            <CodeBlock filename="python">
{`from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="bm_your_key")

# Non-streaming
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain semantic caching."}],
)
print(response.choices[0].message.content)

# Streaming
for chunk in client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain semantic caching."}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="")`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 3. Native Chat */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Native Chat</h2>
            <p className="text-muted-foreground mb-4">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/chat</code> — BitMod native chat format. Returns additional fields like <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">pipeline_trace</code> and <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">sources</code> that are not available through the OpenAI-compatible endpoint.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Request</h3>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/chat \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "query": "What is semantic caching?",
    "model": "gpt-4o-mini",
    "namespace": "default",
    "options": {
      "temperature": 0.7,
      "max_tokens": 256,
      "include_sources": true
    }
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "bm-chat-a1b2c3d4",
  "text": "Semantic caching stores LLM responses indexed by meaning...",
  "model": "gpt-4o-mini",
  "cache_status": "HIT",
  "cache_layer": "semantic_match",
  "latency_ms": 0.8,
  "tokens_used": 0,
  "tokens_saved": 92,
  "pipeline_trace": [
    {"layer": "exact_match", "status": "MISS", "latency_ms": 0.1},
    {"layer": "normalized_match", "status": "MISS", "latency_ms": 0.2},
    {"layer": "semantic_match", "status": "HIT", "latency_ms": 0.5, "similarity": 0.97}
  ],
  "sources": [
    {"type": "cache", "entry_id": "ce-8f2a", "created_at": "2026-03-20T14:30:00Z"}
  ]
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 4. Provider Formats */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Provider Formats</h2>
            <p className="text-muted-foreground mb-4">
              BitMod proxies requests in each provider&apos;s native format. Point any existing SDK at BitMod and it works without code changes.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Anthropic Messages</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/messages</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/messages \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: bm_live_abc123..." \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 256,
    "messages": [
      {"role": "user", "content": "Hello, Claude."}
    ]
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Google Gemini</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1beta/models/{'{model}'}:generateContent</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1beta/models/gemini-2.0-flash:generateContent \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "contents": [
      {"parts": [{"text": "Explain caching."}]}
    ]
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Ollama</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /api/chat</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "llama3.1",
    "messages": [
      {"role": "user", "content": "Explain caching."}
    ],
    "stream": false
  }'`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 5. Search */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Search</h2>
            <p className="text-muted-foreground mb-4">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/search</code> — Semantic search over ingested documents without triggering an LLM call.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Request</h3>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/search \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "query": "cache invalidation strategies",
    "namespace": "docs",
    "top_k": 5,
    "threshold": 0.75
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "results": [
    {
      "id": "doc-3f8a",
      "text": "Cache invalidation can be performed by key, namespace, or TTL expiry...",
      "score": 0.94,
      "metadata": {
        "source": "architecture.md",
        "namespace": "docs",
        "ingested_at": "2026-03-18T10:00:00Z"
      }
    },
    {
      "id": "doc-7b2c",
      "text": "LRU eviction removes the least recently accessed entries when the cache is full...",
      "score": 0.87,
      "metadata": {
        "source": "operations.md",
        "namespace": "docs",
        "ingested_at": "2026-03-18T10:00:00Z"
      }
    }
  ],
  "query": "cache invalidation strategies",
  "latency_ms": 12.4
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Python SDK</h3>
            <CodeBlock filename="python">
{`results = client.search(
    query="cache invalidation strategies",
    namespace="docs",
    top_k=5,
)
for r in results:
    print(f"{r.score:.2f} — {r.text[:80]}")`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 6. Ingestion */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Ingestion</h2>
            <p className="text-muted-foreground mb-4">
              Ingest documents into the vector store for search and document-grounded caching.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Ingest Text</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/ingest/text</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/ingest/text \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "text": "BitMod uses a 9-layer cache pipeline to reduce LLM costs...",
    "namespace": "docs",
    "metadata": {
      "source": "overview.md",
      "author": "team"
    }
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "doc-5e9f",
  "chunks": 3,
  "namespace": "docs",
  "status": "indexed"
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Ingest File</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/ingest/file</code> — Accepts PDF, Markdown, TXT, HTML, CSV, and JSON files.
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/ingest/file \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -F "file=@docs/architecture.pdf" \\
  -F "namespace=docs" \\
  -F "metadata={\"source\":\"architecture.pdf\"}"
`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "doc-8a3b",
  "chunks": 47,
  "namespace": "docs",
  "status": "indexed",
  "file_name": "architecture.pdf",
  "file_size_bytes": 204800
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 7. Cache Management */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Cache Management</h2>

            <h3 className="text-lg font-medium mt-6 mb-3">Get Cache Stats</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/cache/stats</code>
            </p>
            <CodeBlock filename="curl">
{`curl http://localhost:8000/v1/cache/stats \\
  -H "Authorization: Bearer bm_live_abc123..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "total_entries": 4291,
  "valid_entries": 3847,
  "expired_entries": 444,
  "hit_rate": 72.4,
  "total_hits": 12840,
  "total_misses": 4892,
  "avg_hit_latency_ms": 0.9,
  "total_tokens_saved": 1482000,
  "estimated_cost_saved": "$2.22",
  "layers": {
    "exact_match": {"entries": 1200, "hits": 5400},
    "normalized_match": {"entries": 980, "hits": 2100},
    "semantic_match": {"entries": 1400, "hits": 4200},
    "template_match": {"entries": 267, "hits": 1140}
  }
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Invalidate Cache</h3>
            <CodeBlock filename="curl">
{`# Invalidate a specific query
curl -X DELETE http://localhost:8000/v1/cache \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{"query": "What is semantic caching?"}'

# Invalidate by namespace
curl -X DELETE http://localhost:8000/v1/cache/namespace/production \\
  -H "Authorization: Bearer bm_live_abc123..."

# Flush entire cache
curl -X DELETE http://localhost:8000/v1/cache/all \\
  -H "Authorization: Bearer bm_live_abc123..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "status": "ok",
  "entries_removed": 14
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 8. Usage & Analytics */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Usage &amp; Analytics</h2>

            <h3 className="text-lg font-medium mt-6 mb-3">Get Usage Summary</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/usage</code> — Returns aggregated usage data for the current billing period.
            </p>
            <CodeBlock filename="curl">
{`curl http://localhost:8000/v1/usage \\
  -H "Authorization: Bearer bm_live_abc123..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "period": "2026-03-01T00:00:00Z/2026-04-01T00:00:00Z",
  "total_queries": 18420,
  "cache_hits": 13290,
  "cache_misses": 5130,
  "hit_rate": "72.1%",
  "tokens_used": 1024000,
  "tokens_saved": 2890000,
  "estimated_cost": "$1.54",
  "estimated_cost_saved": "$4.34",
  "models": {
    "gpt-4o-mini": {"queries": 12000, "hits": 8900},
    "claude-sonnet-4-20250514": {"queries": 6420, "hits": 4390}
  }
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Export Usage Data</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/usage/export</code> — Download a CSV or JSON export of query-level usage data.
            </p>
            <CodeBlock filename="curl">
{`# JSON export (default)
curl http://localhost:8000/v1/usage/export?format=json \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -o usage.json

# CSV export
curl http://localhost:8000/v1/usage/export?format=csv \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -o usage.csv

# Filter by date range
curl "http://localhost:8000/v1/usage/export?from=2026-03-01&to=2026-03-15&format=csv" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -o usage-march.csv`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 9. Authentication Endpoints */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Authentication Endpoints</h2>

            <h3 className="text-lg font-medium mt-6 mb-3">Create API Key</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/auth/keys</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/auth/keys \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_admin..." \\
  -d '{
    "name": "production-backend",
    "scopes": ["chat", "search", "ingest"],
    "rate_limit": 1000,
    "expires_at": "2027-01-01T00:00:00Z"
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "key-7f2a3b",
  "name": "production-backend",
  "key": "bm_live_sk_7f2a3b...",
  "scopes": ["chat", "search", "ingest"],
  "rate_limit": 1000,
  "created_at": "2026-03-20T14:00:00Z",
  "expires_at": "2027-01-01T00:00:00Z"
}`}
            </CodeBlock>
            <p className="text-sm text-muted-foreground mt-3">
              The full API key is only returned once at creation time. Store it securely.
            </p>

            <h3 className="text-lg font-medium mt-8 mb-3">List API Keys</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/auth/keys</code>
            </p>
            <CodeBlock filename="curl">
{`curl http://localhost:8000/v1/auth/keys \\
  -H "Authorization: Bearer bm_live_admin..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "keys": [
    {
      "id": "key-7f2a3b",
      "name": "production-backend",
      "prefix": "bm_live_sk_7f2a...",
      "scopes": ["chat", "search", "ingest"],
      "rate_limit": 1000,
      "created_at": "2026-03-20T14:00:00Z",
      "last_used_at": "2026-03-27T09:15:00Z"
    }
  ]
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Delete API Key</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">DELETE /v1/auth/keys/{'{id}'}</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X DELETE http://localhost:8000/v1/auth/keys/key-7f2a3b \\
  -H "Authorization: Bearer bm_live_admin..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "status": "deleted",
  "id": "key-7f2a3b"
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Get JWT Token</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/auth/token</code> — Exchange credentials for a short-lived JWT.
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/auth/token \\
  -H "Content-Type: application/json" \\
  -d '{
    "api_key": "bm_live_sk_7f2a3b...",
    "ttl": 3600
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_at": "2026-03-27T15:00:00Z",
  "scopes": ["chat", "search", "ingest"]
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 10. Namespaces */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Namespaces</h2>
            <p className="text-muted-foreground mb-4">
              Namespaces isolate cache entries, documents, and usage metrics. Use them to separate environments, teams, or tenants.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Create Namespace</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/namespaces</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/namespaces \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_admin..." \\
  -d '{
    "name": "production",
    "description": "Production environment cache",
    "settings": {
      "default_ttl": 86400,
      "max_entries": 100000
    }
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "ns-a1b2c3",
  "name": "production",
  "description": "Production environment cache",
  "settings": {
    "default_ttl": 86400,
    "max_entries": 100000
  },
  "created_at": "2026-03-20T14:00:00Z"
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">List Namespaces</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/namespaces</code>
            </p>
            <CodeBlock filename="curl">
{`curl http://localhost:8000/v1/namespaces \\
  -H "Authorization: Bearer bm_live_abc123..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Update Namespace</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">PATCH /v1/namespaces/{'{id}'}</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X PATCH http://localhost:8000/v1/namespaces/ns-a1b2c3 \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_admin..." \\
  -d '{
    "settings": {"default_ttl": 43200}
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Delete Namespace</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">DELETE /v1/namespaces/{'{id}'}</code> — Deletes the namespace and all associated cache entries and documents.
            </p>
            <CodeBlock filename="curl">
{`curl -X DELETE http://localhost:8000/v1/namespaces/ns-a1b2c3 \\
  -H "Authorization: Bearer bm_live_admin..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "status": "deleted",
  "id": "ns-a1b2c3",
  "entries_removed": 2847
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 11. Projects */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Projects</h2>
            <p className="text-muted-foreground mb-4">
              Projects group namespaces, API keys, and usage tracking under a single entity.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Create Project</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/projects</code>
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/projects \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_admin..." \\
  -d '{
    "name": "my-saas-app",
    "description": "Customer-facing chatbot backend"
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "id": "proj-x9y8z7",
  "name": "my-saas-app",
  "description": "Customer-facing chatbot backend",
  "created_at": "2026-03-20T14:00:00Z",
  "namespaces": [],
  "api_keys": 0
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">List Projects</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/projects</code>
            </p>
            <CodeBlock filename="curl">
{`curl http://localhost:8000/v1/projects \\
  -H "Authorization: Bearer bm_live_abc123..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Scan Project</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/projects/{'{id}'}/scan</code> — Scans project resources and returns a health summary.
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/projects/proj-x9y8z7/scan \\
  -H "Authorization: Bearer bm_live_admin..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "project_id": "proj-x9y8z7",
  "status": "healthy",
  "namespaces": 3,
  "total_cache_entries": 8420,
  "total_documents": 142,
  "active_api_keys": 2,
  "issues": []
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 12. Conversation History */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Conversation History</h2>

            <h3 className="text-lg font-medium mt-6 mb-3">List Conversations</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">GET /v1/history</code> — Returns recent conversation turns.
            </p>
            <CodeBlock filename="curl">
{`curl "http://localhost:8000/v1/history?limit=20&offset=0" \\
  -H "Authorization: Bearer bm_live_abc123..."`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "conversations": [
    {
      "id": "conv-4a5b6c",
      "query": "What is semantic caching?",
      "response": "Semantic caching stores LLM responses indexed by meaning...",
      "model": "gpt-4o-mini",
      "cache_status": "HIT",
      "latency_ms": 0.8,
      "created_at": "2026-03-27T09:15:00Z",
      "rating": null
    }
  ],
  "total": 1847,
  "limit": 20,
  "offset": 0
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Rate a Response</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/history/{'{id}'}/rate</code> — Submit a thumbs-up/down rating to improve cache quality.
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/history/conv-4a5b6c/rate \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "rating": "positive",
    "comment": "Accurate and concise"
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-8 mb-3">Correct a Response</h3>
            <p className="text-sm text-muted-foreground mb-3">
              <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">POST /v1/history/{'{id}'}/correct</code> — Submit a corrected response. BitMod updates the cache entry.
            </p>
            <CodeBlock filename="curl">
{`curl -X POST http://localhost:8000/v1/history/conv-4a5b6c/correct \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer bm_live_abc123..." \\
  -d '{
    "corrected_response": "Semantic caching stores responses keyed by the meaning of the query, using vector embeddings..."
  }'`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-4 mb-3">Response</h3>
            <CodeBlock filename="json">
{`{
  "status": "corrected",
  "id": "conv-4a5b6c",
  "cache_updated": true
}`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 13. Health & Monitoring */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Health &amp; Monitoring</h2>
            <p className="text-muted-foreground mb-4">
              Unauthenticated health endpoints for load balancers, orchestrators, and monitoring systems.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Endpoint</th>
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Method</th>
                    <th className="text-left py-2 text-muted-foreground font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">/health</td>
                    <td className="py-2 pr-4">GET</td>
                    <td className="py-2">Basic liveness check. Returns 200 if the process is alive.</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">/healthz</td>
                    <td className="py-2 pr-4">GET</td>
                    <td className="py-2">Kubernetes liveness probe. Identical to /health.</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">/readyz</td>
                    <td className="py-2 pr-4">GET</td>
                    <td className="py-2">Readiness probe. Returns 200 only when all dependencies (DB, cache) are connected.</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 font-mono text-primary/80">/metrics</td>
                    <td className="py-2 pr-4">GET</td>
                    <td className="py-2">Prometheus-format metrics (request count, latency histograms, cache stats).</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <CodeBlock filename="curl">
{`curl http://localhost:8000/health

# {"status": "ok", "version": "0.1.0", "uptime_s": 84200}

curl http://localhost:8000/readyz

# {
#   "status": "ready",
#   "checks": {
#     "database": "ok",
#     "cache": "ok",
#     "vector_store": "ok"
#   }
# }`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 14. Response Headers */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Response Headers</h2>
            <p className="text-muted-foreground mb-4">
              Every proxied response includes BitMod headers with cache and performance metadata.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Header</th>
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Example</th>
                    <th className="text-left py-2 text-muted-foreground font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-Bitmod-Cache</td>
                    <td className="py-2 pr-4 font-mono">HIT</td>
                    <td className="py-2">Cache result: <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">HIT</code>, <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">MISS</code>, or <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">BYPASS</code></td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-Bitmod-Latency</td>
                    <td className="py-2 pr-4 font-mono">0.8ms</td>
                    <td className="py-2">Total gateway processing time including cache lookup</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-Bitmod-Model</td>
                    <td className="py-2 pr-4 font-mono">gpt-4o-mini</td>
                    <td className="py-2">Model that generated the response (or served from cache)</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-Bitmod-Layer</td>
                    <td className="py-2 pr-4 font-mono">semantic_match</td>
                    <td className="py-2">Which cache layer produced the hit (absent on MISS)</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-Bitmod-Tokens-Saved</td>
                    <td className="py-2 pr-4 font-mono">92</td>
                    <td className="py-2">Number of tokens saved by the cache hit</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-Bitmod-Request-Id</td>
                    <td className="py-2 pr-4 font-mono">req-9f1a2b3c</td>
                    <td className="py-2">Unique request ID for debugging and support</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <CodeBlock filename="terminal">
{`curl -v http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello"}]}'

# < X-Bitmod-Cache: HIT
# < X-Bitmod-Latency: 0.8ms
# < X-Bitmod-Model: gpt-4o-mini
# < X-Bitmod-Layer: exact_match
# < X-Bitmod-Tokens-Saved: 14
# < X-Bitmod-Request-Id: req-9f1a2b3c`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 15. Error Handling */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Error Handling</h2>
            <p className="text-muted-foreground mb-4">
              All errors follow a consistent JSON format. The HTTP status code is always set appropriately.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Error Format</h3>
            <CodeBlock filename="json">
{`{
  "error": {
    "type": "invalid_request_error",
    "message": "The 'model' field is required.",
    "param": "model",
    "code": "missing_required_field"
  },
  "request_id": "req-9f1a2b3c"
}`}
            </CodeBlock>

            <h3 className="text-lg font-medium mt-6 mb-3">Status Codes</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Code</th>
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Type</th>
                    <th className="text-left py-2 text-muted-foreground font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">400</td>
                    <td className="py-2 pr-4">invalid_request_error</td>
                    <td className="py-2">Malformed request body or missing required fields</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">401</td>
                    <td className="py-2 pr-4">authentication_error</td>
                    <td className="py-2">Missing or invalid API key / JWT</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">403</td>
                    <td className="py-2 pr-4">permission_error</td>
                    <td className="py-2">Key lacks the required scope for this endpoint</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">404</td>
                    <td className="py-2 pr-4">not_found_error</td>
                    <td className="py-2">Resource not found (namespace, project, conversation)</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">429</td>
                    <td className="py-2 pr-4">rate_limit_error</td>
                    <td className="py-2">Rate limit exceeded. See Retry-After header.</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">500</td>
                    <td className="py-2 pr-4">internal_error</td>
                    <td className="py-2">Unexpected server error</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 font-mono text-primary/80">502</td>
                    <td className="py-2 pr-4">upstream_error</td>
                    <td className="py-2">LLM provider returned an error or timed out</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* 16. Rate Limiting */}
          {/* ------------------------------------------------------------------ */}
          <section>
            <h2 className="text-2xl font-semibold mb-2">Rate Limiting</h2>
            <p className="text-muted-foreground mb-4">
              Rate limits are applied per API key. Every response includes rate-limit headers so your application can adapt.
            </p>

            <h3 className="text-lg font-medium mt-6 mb-3">Rate Limit Headers</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Header</th>
                    <th className="text-left py-2 text-muted-foreground font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-RateLimit-Limit</td>
                    <td className="py-2">Maximum requests per minute for this key</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-RateLimit-Remaining</td>
                    <td className="py-2">Requests remaining in the current window</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">X-RateLimit-Reset</td>
                    <td className="py-2">Unix timestamp when the window resets</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 font-mono text-primary/80 whitespace-nowrap">Retry-After</td>
                    <td className="py-2">Seconds to wait before retrying (only on 429)</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h3 className="text-lg font-medium mt-6 mb-3">Default Tiers</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Tier</th>
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Requests / min</th>
                    <th className="text-left py-2 text-muted-foreground font-medium">Burst</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4">Free</td>
                    <td className="py-2 pr-4 font-mono text-primary/80">60</td>
                    <td className="py-2 font-mono text-primary/80">10</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4">Standard</td>
                    <td className="py-2 pr-4 font-mono text-primary/80">600</td>
                    <td className="py-2 font-mono text-primary/80">50</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4">Pro</td>
                    <td className="py-2 pr-4 font-mono text-primary/80">3000</td>
                    <td className="py-2 font-mono text-primary/80">200</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Enterprise</td>
                    <td className="py-2 pr-4 font-mono text-primary/80">Custom</td>
                    <td className="py-2 font-mono text-primary/80">Custom</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="text-sm text-muted-foreground mt-4">
              Cache hits do not count against your rate limit. Self-hosted deployments can override these defaults in <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">bitmod.yaml</code>.
            </p>

            <CodeBlock filename="python">
{`import time
from openai import OpenAI, RateLimitError

client = OpenAI(base_url="http://localhost:8000/v1", api_key="bm_your_key")

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
except RateLimitError as e:
    retry_after = float(e.response.headers.get("Retry-After", 1))
    print(f"Rate limited. Retrying in {retry_after}s...")
    time.sleep(retry_after)
    # retry the request`}
            </CodeBlock>
          </section>

          {/* ------------------------------------------------------------------ */}
          {/* Summary card */}
          {/* ------------------------------------------------------------------ */}
          <Card className="border-border/40 bg-card/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary/10 p-2">
                  <Book className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold mb-1">Quick Reference</h3>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>All endpoints live under <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">http://localhost:8000</code> by default.</li>
                    <li>Authenticate with <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">Authorization: Bearer bm_...</code> or a JWT token.</li>
                    <li>Every response includes <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">X-Bitmod-*</code> headers with cache and latency metadata.</li>
                    <li>Cache hits are free — they don&apos;t consume tokens or count against rate limits.</li>
                    <li>Use the native <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">/v1/chat</code> endpoint for full pipeline traces and source attribution.</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Next Steps */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Next Steps</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Link href="/guides/getting-started" className="group">
                <Card className="h-full border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300">
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="rounded-lg bg-primary/10 p-2 shrink-0">
                      <Zap className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">Getting Started</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Install and send your first query</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                  </CardContent>
                </Card>
              </Link>
              <Link href="/guides/cache-setup" className="group">
                <Card className="h-full border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300">
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="rounded-lg bg-primary/10 p-2 shrink-0">
                      <Database className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">Cache Setup Guide</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Configure TTL, layers, and monitoring</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                  </CardContent>
                </Card>
              </Link>
            </div>
          </section>
        </div>
      </article>
    </div>
  )
}
