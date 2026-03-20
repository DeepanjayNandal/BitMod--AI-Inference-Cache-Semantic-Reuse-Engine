# Bitmod — Architecture

**Modular AI Data Infrastructure. Compute once, serve forever.**

---

## What Bitmod Is

Bitmod is the accuracy and efficiency layer between data and AI. It ingests data from any source, normalizes it, version-tracks it, and serves it through a patented caching engine that ensures every AI-generated answer — and every AI agent action plan — is accurate, current, and never computed twice.

The system implements 36 interconnected subsystems covered by 71 patent claims across 38 sections.

---

## Core Loops

### Answer Loop
```
Ingest → Version → Cache → Serve → Monitor Source → Detect Change →
Invalidate → Re-ingest → Re-cache → Serve
```

### Agent Loop
```
Task Request → Generate Plan → Approve → Execute → Cache Plan →
Re-execute with New Parameters → Detect Source Change →
Invalidate Plan → Re-generate → Re-approve → Cache
```

---

## 36 Subsystems (Patent-Mapped)

Each subsystem is a modular, independently deployable component. The system is designed so that
any subsystem can be a library embedded in another service OR a standalone microservice — the
boundary is a deployment decision, not an architectural one.

### I. Core Data Layer

| # | Subsystem | Patent § | Service | Purpose |
|---|-----------|----------|---------|---------|
| 1 | Data Ingestion & Versioning | §II | `ingest` | Pluggable ingestors, multi-format acquisition, version-aware upserts |
| 2 | Source Data Store | §III | `postgres` | 3-tier hierarchical schema (documents → sections → chunks) |
| 3 | Source Monitoring | §IV | `monitor` | Autonomous agents polling sources (ETag, hash, RSS, API) |
| 4 | Change Events | §V | `monitor` | Records changes, triggers invalidation pipeline |

### II. Intelligence Layer

| # | Subsystem | Patent § | Service | Purpose |
|---|-----------|----------|---------|---------|
| 5 | Tiered AI Response Generation | §VI | `chat` | LLM routing by tier, tool-calling, source retrieval |
| 6 | Parameterized Answer Cache | §VII | `core` (lib) | SHA-256 composite keying, source-version locking |
| 7 | Invalidation Engine | §VIII | `invalidator` | Change-driven invalidation + serve-time double verification |
| 8 | Notification System | §IX | `notifier` | Change alerts to subscribed users (email, push, in-app) |
| 9 | Gap Detection | §X | `chat` | Captures missing data, prioritized acquisition queue |
| 10 | Hierarchical Filter Resolution | §XI | `core` (lib) | Multi-level contextual parameter resolution |

### III. Intent-Aware Assembly Layer

| # | Subsystem | Patent § | Service | Purpose |
|---|-----------|----------|---------|---------|
| 11 | Intent Detection | §XXVIII | `core` (lib) | Classify user intent (cite, summarize, theorize, compare, execute, etc.) via rule engine + LLM fallback |
| 12 | Block Resolver | §XXIX | `core` (lib) | Retrieve and compress content blocks at intent-appropriate granularity (full, structured, headline) |
| 13 | Role Router | §XXX | `core` (lib) | Assign LLM role (narrator, synthesizer, reasoner, agent) with scoped prompt, token budget, and model tier |
| 14 | Response Assembly | §XXXI | `core` (lib) | Combine cached blocks + role-scoped LLM output into final answer. Assembly itself is cached. |
| 15 | Multi-Tenant Isolation | §XXXII | `core` (lib) | Tenant-scoped cache keys, access control on blocks/answers, cross-tenant sharing opt-in |

### IV. Agent Execution Layer

| # | Subsystem | Patent § | Service | Purpose |
|---|-----------|----------|---------|---------|
| 16 | Cached Action Plans | §XIII | `executor` | Zero-reasoning deterministic replay via parameter injection |
| 17 | Agent Security | §XIV | `executor` | HMAC integrity, typed params, tool scope, sandbox, approvals |

### V. Advanced Caching Layer

| # | Subsystem | Patent § | Service | Purpose |
|---|-----------|----------|---------|---------|
| 18 | Composable Query Decomposition | §XV | `core` (lib) | Sub-query splitting, independent cache per component |
| 19 | Multi-Modal Caching | §XVI | `core` (lib) | Charts, tables, audio, exports — each modality cached independently |
| 20 | Federated Cache Sharing | §XVII | `federation` | Cross-org cache reuse with source-version cross-validation |
| 21 | Predictive Cache Warming | §XVIII | `warmer` | Pattern analysis → pre-generate answers before users ask |
| 22 | Temporal Queries | §XIX | `core` (lib) | Point-in-time historical queries, permanently valid cache entries |
| 23 | Cache-Informed Model Improvement | §XX | `trainer` | Validated Q&A corpus → fine-tuning, correction triples |
| 24 | Cross-Lingual Cache Sharing | §XXI | `core` (lib) | Language-normalized canonical keys, translation-layer cache |
| 25 | Adaptive Storage Tiering | §XXII | `core` (lib) | Hot/warm/cold tiers, cost-aware eviction, invalidation-aware promotion |
| 26 | Expert Review | §XXIII | `review` | Domain expert corrections, confidence scoring, preference signals |
| 27 | Response Versioning | §XXIV | `core` (lib) | Version chains, differential display, compliance audit |
| 28 | Semantic Cache Matching | §XXXIII | `core` (lib) | Embedding-based cache lookup — cosine similarity on query vectors for near-match retrieval |
| 29 | Probabilistic Confidence Accumulation | §XXXIV | `core` (lib) | Bayesian evidence composition across all cache layers — multi-signal serve decisions |
| 30 | Cluster-Organized Semantic Cache | §XXXV | `core` (lib) | HNSW-indexed cluster centroids for O(log K) semantic matching with adversarial resistance |
| 31 | LLM-Verified Cache Promotion | §XXXVI | `core` (lib) | Asynchronous LLM judge verifies near-miss matches and promotes to high-confidence tier |
| 32 | Learning-Based Cache Eviction | §XXXVII | `core` (lib) | Frequency prediction × regeneration cost joint optimization for eviction decisions |
| 33 | Post-Generation Cache Learning | §XXXVIII | `core` (lib) | Atomic fact decomposition + similarity link construction after every LLM call |

### VI. Platform Layer

| # | Subsystem | Patent § | Service | Purpose |
|---|-----------|----------|---------|---------|
| 29 | Adaptive Resource Allocation | §XXV | `orchestrator` | Dynamic compute/storage/regeneration balancing |
| 30 | User Application Layer | — | `frontend` | Web + mobile interfaces |
| 31 | Microservice Architecture | §XXVII | `gateway` | Containerized services, embedded cache lib, any topology |

---

## Intelligent Cache Engine (Deep Design)

The cache engine is Bitmod's core innovation. It uses a **Bayesian evidence accumulation** model —
all layers contribute graded confidence scores that are composed probabilistically. The system
serves when accumulated confidence reaches 0.95; below that threshold, cached context assists
the LLM rather than replacing it entirely.

**Key properties:**
- **Not winner-take-all.** Multiple layers can contribute partial evidence to the same query.
- **Semantic cache returns top 3 matches** above 0.75 (not just the single best).
- **Post-generation learning:** Every LLM call produces atomic facts and similarity links that improve future cache performance.
- **New layers:** Similarity link traversal (learned near-miss graph) and atomic fact search (reusable facts decomposed from prior answers).

### Layer 1: Parameterized Answer Cache

**Composite Key Generation:**
```
answer_key = SHA-256(
    normalize(query)
    | intent                ← response style (cite, summarize, theorize, etc.)
    | tenant_id             ← multi-tenant isolation
    | filter1:value         ← unlimited filter parameters (sorted alphabetically)
    | filter2:value
    | ...filterN:value      ← supports 50+ filters deep
    | temporal_scope        ← point-in-time queries
    | language              ← cross-lingual support
)
```
Filters are arbitrary key-value pairs. The system imposes no limit on filter depth —
any unique combination of parameters produces a distinct cache entry. Filter keys are
sorted alphabetically before hashing so `{a:1, b:2}` = `{b:2, a:1}`.

**Source-Data Manifest** (attached to every cached answer):
```json
{
    "sections_consulted": [
        {
            "section_id": "uuid",
            "citation": "42 U.S.C. § 1983",
            "version": 3,
            "version_hash": "sha256:abc123...",
            "consulted_at": "2026-03-19T12:00:00Z"
        }
    ],
    "model_used": "claude-sonnet-4-20250514",
    "generation_ms": 2340,
    "confidence": 0.92
}
```

**Double Verification** (at serve time):
1. Receive cache hit for answer_key
2. For each section in source_manifest:
   - Query current version_hash from sections table
   - Compare against manifest's recorded hash
3. ALL hashes match → serve cached answer, increment serve_count
4. ANY hash mismatch → invalidate, queue for regeneration, fall through to fresh generation

### Layer 2: Fuzzy Query Matching (Patent §XII)

When exact cache lookup misses:
1. Search cached answer_cache entries with matching filter parameters
2. Compute similarity between new query and cached question_normalized values
3. If similarity > threshold (e.g., 0.85):
   - Present similar cached query to user for confirmation
   - User confirms → serve cached answer at zero compute cost
   - User declines → proceed with fresh generation
4. Converts cache misses into cache hits without any LLM call

### Layer 3: Composable Query Decomposition (Patent §XV)

Complex queries are decomposed into independently cacheable sub-queries:
```
"Compare employment termination rules in CA vs TX"
  ↓ decompose
  Sub-query 1: "employment termination rules" + jurisdiction=CA
  Sub-query 2: "employment termination rules" + jurisdiction=TX
  ↓ independent cache lookup
  Sub-query 1: CACHE HIT (answered last week)
  Sub-query 2: CACHE MISS (generate fresh)
  ↓ synthesize
  Final answer: comparison using cached CA + fresh TX
```

Each sub-query has its own source manifest and invalidates independently.

### Layer 4: Cached Action Plans (Patent §XIII)

Agent tasks are cached as structured execution plans:
```json
{
    "plan_id": "uuid",
    "intent_key": "sha256(normalized_intent + filters)",
    "steps": [
        {
            "tool": "search_data",
            "parameters": {"query": "{query}", "jurisdiction": "{jurisdiction}"},
            "output_binding": "search_results"
        },
        {
            "tool": "get_section",
            "parameters": {"section_id": "{search_results[0].section_id}"},
            "output_binding": "full_text"
        },
        {
            "tool": "format_report",
            "parameters": {"sections": "{full_text}", "template": "compliance"},
            "output_binding": "report"
        }
    ],
    "parameter_slots": {
        "query": {"type": "string", "required": true},
        "jurisdiction": {"type": "string", "pattern": "^[A-Z]{2}$"}
    },
    "allowed_tools": ["search_data", "get_section", "format_report"],
    "forbidden_tools": ["delete_data", "admin_*"],
    "source_manifest": [...],
    "hmac_signature": "sha256-hmac:...",
    "approval": {
        "approved_by": "user_id",
        "approved_at": "2026-03-19T12:00:00Z",
        "expires_at": "2026-04-19T12:00:00Z",
        "max_executions": 1000,
        "parameter_constraints": {"jurisdiction": ["CA", "TX", "NY"]}
    }
}
```

**Security guarantees (Patent §XIV):**
- HMAC integrity verification on every execution
- Typed parameter validation (injection impossible)
- Tool scope enforcement (plan can't escalate privileges)
- Execution sandbox (step outputs can't modify subsequent steps)
- Scoped expiring approvals (bound to plan hash + parameter constraints)
- Immutable audit trail (every execution recorded)

### Layer 5: Adaptive Storage Tiering (Patent §XXII)

```
Hot Tier  (Redis)     ← frequently accessed, <1ms serve time
Warm Tier (PostgreSQL) ← moderate access, <10ms serve time
Cold Tier (S3/disk)    ← archival, <100ms serve time
```

**Promotion/Demotion Rules:**
- serve_count > 10 in 24h → promote to Hot
- serve_count = 0 for 7 days → demote to Cold
- Cost-aware: expensive-to-regenerate answers (long generation_ms, high model tier) resist eviction
- Invalidation-aware: answers referencing frequently-changing sources suppressed from Hot tier

### Layer 6: Predictive Cache Warming (Patent §XVIII)

Two warming strategies:
1. **Pattern-based**: Analyze query history → predict likely future queries → pre-generate during off-peak
2. **Change-triggered**: Source data changes → predict which queries will be asked about the change → pre-generate answers before users ask

### Layer 7: Temporal Queries (Patent §XIX)

Queries with a time dimension:
```
"What was the minimum wage in CA as of January 2025?"
  ↓
  answer_key includes temporal_scope = "2025-01-01"
  ↓
  System retrieves section versions current as of that date
  ↓
  Cached answer is PERMANENTLY VALID (historical data doesn't change)
  ↓
  Exempt from invalidation — never expires
```

### Layer 8: Response Versioning (Patent §XXIV)

Every regenerated answer links to its predecessor:
```
Answer v1 (2026-01-15) → invalidated (source changed 2026-03-01)
  ↓
Answer v2 (2026-03-01) → current
  ↓
Differential display: "Section 1983 was amended on 2026-02-28.
  Previous answer referenced version 3. Current answer references version 4.
  Change: [inline diff of what changed in the source]"
```

### Layer 9: Federated Cache Sharing (Patent §XVII)

Multiple Bitmod deployments share cache across organizational boundaries:
```
Org A asks: "HIPAA requirements for telehealth"
  → generates answer, caches locally

Org B asks same question:
  → local cache miss
  → federated query (sends composite hash only, NOT raw query text)
  → Org A responds with cached answer + source manifest
  → Org B independently verifies source versions against its own data
  → All versions match → serve federated answer
  → Any version mismatch → reject, generate locally
```

Privacy-preserving: only SHA-256 hashes cross organizational boundaries.

---

## Intent-Aware Assembly Engine (Deep Design)

The assembly engine is Bitmod's second core innovation. It decomposes the LLM's monolithic role
into intent detection → block retrieval → role-scoped generation → cached assembly.

### Why This Exists

Traditional RAG: stuff everything into context, let the LLM figure it out. Burns maximum tokens,
maximum cost, maximum hallucination surface area. The LLM is simultaneously doing retrieval
interpretation, reasoning, formatting, citation, and synthesis — all in one call.

Build-a-Block: facts come from the database (verified, cached). The LLM only does the work that
actually requires intelligence. Everything else is retrieval + assembly.

### Intent Spectrum

```
PASSIVE ◄────────────────────────────────────► ACTIVE

cite        summarize     think        execute      plan
list        explain       hypothesize  build        automate
quote       compare       analyze      deploy       orchestrate
reference   contrast      theorize     transform    schedule

◄── More cacheable              Less cacheable ──►
◄── Less LLM                    More LLM       ──►
◄── Cheaper models              Expensive models──►
◄── Chat mode                   Agent mode      ──►

The retrieval layer is SHARED across the entire spectrum.
Only the role assignment and assembly template differ.
```

### Intent Detection

Three-tier classification with increasing cost:

**Tier 1: Rule Engine (0ms, $0)**
Pattern matching on query structure. Handles ~70% of queries.
```
"what is X"          → EXPLAIN
"list X"             → LIST
"compare X vs Y"     → COMPARE
"cite X"             → CITE
"summarize X"        → SUMMARIZE
"what if X"          → HYPOTHESIZE
"produce N scenarios"→ THINK
"how does X work"    → EXPLAIN
"create/build/make X"→ EXECUTE
```

**Tier 2: Local Classifier (1ms, $0)**
Lightweight model (logistic regression or small transformer) trained on labeled query→intent pairs.
Handles ~25% of queries where rule engine confidence < 0.7.

**Tier 3: LLM Classification (200ms, ~$0.001)**
Cheap/fast LLM call with constrained output. Handles ~5% of genuinely ambiguous queries.
Only fires when Tier 1+2 confidence < 0.5.

**Intent output:**
```json
{
    "action": "COMPARE",
    "format": "STRUCTURED",
    "depth": "DETAILED",
    "entities": ["DUI", "AZ", "CA"],
    "mode": "INFORMATIONAL",
    "confidence": 0.95,
    "tier": 1
}
```

### Intent Registry (Plugin Architecture)

Each intent is a YAML config file. Adding new intents = adding a file, no code changes.

```yaml
# intents/compare.yaml
name: compare
description: Side-by-side comparison of two or more entities
triggers:
  patterns: ["compare .+ vs", "difference between", "X vs Y", "contrast"]
  min_entities: 2
role: structurer
compression: structured
token_budget: 800
model_tier: cheap          # narrator|cheap|standard|expensive
cache_ttl: forever         # forever|24h|1h|none
cacheable: true
template: comparison       # assembly template name
```

```yaml
# intents/theorize.yaml
name: theorize
description: Open-ended reasoning and scenario generation
triggers:
  patterns: ["what if", "hypothesize", "theorize", "scenario", "outcome"]
role: reasoner
compression: full
token_budget: 4000
model_tier: expensive
cache_ttl: 1h             # reasoning may evolve with model updates
cacheable: true
template: analysis
```

```yaml
# intents/execute.yaml
name: execute
description: Agentic task execution with tool calling
triggers:
  patterns: ["create", "build", "deploy", "update", "delete", "run"]
role: agent
compression: full
token_budget: 8000
model_tier: expensive
cache_ttl: none            # agent actions are not cached (plans are)
cacheable: false
template: null             # no template — free-form agent output
requires_approval: true
```

### Content Blocks

Blocks are pre-computed, intent-agnostic content units stored alongside sections.
A single section can produce blocks at multiple compression levels.

**Block Model:**
```
Section "AZ § 28-1381 — DUI"
  ├── Block (full)        → complete statute text (1,200 tokens)
  ├── Block (structured)  → {bac: "0.08", class: "1 misdemeanor",
  │                          jail: "10d-180d", fine: "$250-$2500",
  │                          license: "90d-1yr suspension"}  (80 tokens)
  └── Block (headline)    → "AZ DUI: BAC ≥0.08, Class 1 misd, 10-180d jail" (15 tokens)
```

**Compression levels:**
- **Full** — complete source text. Used for THEORIZE, ANALYZE, THINK intents.
- **Structured** — extracted key-value facts. Used for COMPARE, CITE, LIST intents.
- **Headline** — one-line summary. Used for SUMMARIZE, overview contexts.

Blocks are generated at ingestion time (not query time). Cost: one extraction pass per section.
After that, blocks are served from cache forever (until source changes).

**Block versioning:** When a source section changes, all its blocks are invalidated and
regenerated. The block version_hash links to the section version_hash, so the existing
double-verification system works unchanged.

### Role Router

The LLM's role is determined by the detected intent. Each role has:
- A scoped system prompt (narrow instructions, not "do everything")
- A token budget (narrator gets 200 tokens of context, reasoner gets 4000)
- A model tier (narrator → local/cheap, reasoner → expensive)
- A cacheability flag (narrator output highly cacheable, agent output not)

**Role → Model mapping (configurable):**
```yaml
roles:
  narrator:
    model: ollama/llama3.2       # local, free
    max_input_tokens: 500
    max_output_tokens: 500
    system_prompt: "Format these verified facts into readable prose. Do not add information."

  synthesizer:
    model: anthropic/haiku       # cheap cloud
    max_input_tokens: 1500
    max_output_tokens: 1000
    system_prompt: "Synthesize these facts into a coherent summary. Cite sources."

  structurer:
    model: anthropic/haiku       # cheap cloud
    max_input_tokens: 2000
    max_output_tokens: 1500
    system_prompt: "Organize these facts into a structured comparison. Use tables."

  reasoner:
    model: anthropic/sonnet      # standard cloud
    max_input_tokens: 4000
    max_output_tokens: 2000
    system_prompt: "Analyze these facts and provide reasoned conclusions."

  explorer:
    model: anthropic/opus        # expensive cloud
    max_input_tokens: 8000
    max_output_tokens: 4000
    system_prompt: "Explore multiple hypotheses. Consider edge cases."

  agent:
    model: anthropic/sonnet      # needs tool-calling
    max_input_tokens: 8000
    max_output_tokens: 4000
    tools: true
```

### Assembly Pipeline

```
User Query
    │
    ▼
┌─── Intent Detection ────────────────────────┐
│  Rule Engine → Local Classifier → LLM       │
│  Output: action, format, depth, entities     │
└──────────────┬──────────────────────────────-┘
               │
               ▼
┌─── Cache Check ─────────────────────────────┐
│  Key = SHA-256(query | intent | filters)     │
│  Hit? → double-verify → serve               │
│  Miss? → continue                            │
└──────────────┬──────────────────────────────-┘
               │
               ▼
┌─── Block Resolver ──────────────────────────┐
│  Retrieve relevant sections (existing search)│
│  Select compression level per intent         │
│  CITE/COMPARE → structured blocks            │
│  THEORIZE     → full blocks                  │
│  SUMMARIZE    → headline blocks              │
│  Blocks come from block cache (pre-computed)  │
└──────────────┬──────────────────────────────-┘
               │
               ▼
┌─── LLM Role Assignment ────────────────────-┐
│  Intent → Role → Model + Prompt + Budget     │
│  Compressed blocks injected as context       │
│  LLM generates ONLY the synthesis/framing    │
└──────────────┬──────────────────────────────-┘
               │
               ▼
┌─── Assembly ────────────────────────────────┐
│  Template-driven combination:                │
│  - Cached blocks (verified facts)            │
│  - LLM output (synthesis/framing)            │
│  - Citations (from block metadata)           │
│  - Format structure (from intent template)   │
│  Result cached with full composite key       │
└──────────────┬──────────────────────────────-┘
               │
               ▼
           Response
```

### Three-Level Cache

The assembly engine introduces three cache tiers:

| Level | What's Cached | Key | TTL | Reuse |
|-------|--------------|-----|-----|-------|
| **Block Cache** | Pre-compressed content per section per compression level | section_id + compression_level | Until source changes | Highest — same block serves every intent |
| **Assembly Cache** | Complete assembled answers | query + intent + filters + tenant | Per intent config | High — identical query+intent combos |
| **Plan Cache** | Agentic execution plans | intent_key + parameter_types | Per approval scope | Medium — plans reused with different parameters |

### Multi-Tenant Isolation

Tenant ID is a first-class component of every cache key:

```
answer_key = SHA-256(
    normalize(query)
    | intent
    | tenant_id              ← NEW
    | filter1:value
    | filter2:value
    | ...filterN:value       ← supports unlimited filters
    | temporal_scope
    | language
)
```

**Isolation guarantees:**
- Tenant A's cache entries are invisible to Tenant B
- Block cache is shared by default (same statute is the same statute) but can be tenant-scoped
- Assembly cache is always tenant-scoped (different tenants may have different data access)
- Cross-tenant sharing is opt-in via federation (existing §XVII)

**Filter depth:** The cache key supports unlimited filter parameters. Each unique filter
combination produces a distinct cache entry. The filter set is sorted alphabetically
before hashing, so `{a:1, b:2}` and `{b:2, a:1}` produce the same key.

### Semantic Cache Matching

When exact cache lookup misses AND fuzzy text matching misses, fall back to embedding-based
similarity search:

1. At cache store time: embed the normalized query, store alongside the cache entry
2. At cache miss time: embed the new query, search cached query embeddings by cosine similarity
3. Threshold > 0.92 → serve cached answer (high confidence match)
4. Threshold 0.85-0.92 → present to user for confirmation (fuzzy match behavior)
5. Threshold < 0.85 → genuine miss, generate fresh

This solves: "DUI penalties in Arizona" vs "What are the consequences for drunk driving in AZ"
→ same meaning, different words, caught by semantic matching.

### Probabilistic Confidence Accumulation (Patent §XXXIV)

The cache engine's core innovation: instead of winner-take-all (first layer to hit serves), ALL layers
contribute graded confidence scores composed using Bayesian probability:

```
total_confidence = 1.0 − (1 − exact) × (1 − semantic) × (1 − fuzzy) × (1 − composable) × (1 − links) × (1 − facts)
```

**Three cost tiers based on accumulated confidence:**
- **≥ 0.95**: Serve from cache. Zero LLM cost. ~16ms total.
- **0.30 – 0.94**: Context-assisted generation. LLM receives all cached evidence as pre-loaded context, reducing generation from ~800 tokens to ~200 tokens. 50-80% cost reduction.
- **< 0.30**: Full cache miss. Standard LLM generation.

Multiple weak signals compose into strong decisions. Example: semantic at 0.68 + fuzzy at 0.38 + fact at 0.36 = total 0.88. Add one similarity link at 0.39 → total 0.93. One more fact → crosses 0.95, served without LLM.

**Correlation-aware adjustment:** Layers evaluating overlapping data (e.g., exact + semantic both matching the same entry) apply a correlation discount to prevent double-counting.

**Negative evidence:** Stale source detection can *subtract* confidence, preventing serves when source data has changed but invalidation hasn't propagated yet.

### Cluster-Organized Semantic Cache (Patent §XXXV)

At scale, brute-force embedding comparison (O(n)) breaks. The cluster-organized cache solves this:

```
Stage 1 (Coarse): query → compare against K cluster centroids → select candidate clusters
Stage 2 (Fine):   query → compare against M members within candidates → return best match
```

Complexity: O(K + M) instead of O(N). With HNSW index on centroids: O(log K + M).

**Adversarial resistance:** An adversarial prompt crafted to game a single cached entry must ALSO
be close to that entry's cluster centroid. Since centroids represent the mean of many legitimate
queries, single-target attacks fail the coarse filter. Outlier queries falling between all clusters
are flagged and routed directly to the LLM.

### LLM-Verified Cache Promotion (Patent §XXXVI)

For near-miss matches (0.80-0.95 similarity), optionally invoke an LLM judge asynchronously:

```
Verdict: ACCEPT  → create new cache entry for this query, mark as LLM-verified (higher base confidence)
Verdict: PARTIAL → use cached answer as context, LLM supplements (50-80% cost reduction)
Verdict: REJECT  → full generation
```

Verification cost is amortized: one cheap LLM call to verify, then every future identical query is
a zero-cost cache hit. The system tracks amortized savings and flags entries where verification
cost exceeds cumulative savings.

### Learning-Based Cache Eviction (Patent §XXXVII)

Replaces static LRU/LFU with a joint optimization:

```
eviction_score = predicted_future_accesses × regeneration_cost × source_stability
```

- **Predicted accesses**: Exponentially-decaying rate + periodicity detection + trend indicator
- **Regeneration cost**: Model tier × token count × per-token price
- **Source stability**: Penalizes entries referencing frequently-changing sources (likely to be invalidated before next access)

Entries with lowest scores evicted first. Model updates incrementally per access event (no batch retraining).

### Post-Generation Cache Learning (Patent §XXXVIII)

Every LLM response produces two reusable artifacts:

**1. Atomic Facts** — Self-contained factual assertions extracted from the response:
```
Response: "California applies a source-based tax rule for remote workers. The FTB considers
          work-from-home as California-source income."
  ↓ decompose
  Fact 1: "California applies a source-based tax rule for remote workers" [entity: California, category: rule]
  Fact 2: "FTB considers work-from-home as California-source income" [entity: FTB, category: rule]
```
Each fact is embedded and stored. Future queries on related topics find these facts via embedding
similarity, contributing evidence to Bayesian accumulation even when no complete cached answer exists.

**2. Similarity Links** — Learned relationships between queries:
```
New query generates answer despite 0.88 near-miss from "California remote work tax rules"
  ↓ create link
  Link: new_entry ↔ near_miss (similarity: 0.88, bidirectional, decaying)
```
Future queries that hit the near-miss entry follow links to discover the new entry. Links decay over time
unless reinforced by successful serves. Multi-hop traversal (2 hops default) discovers transitive relationships.

**The compounding effect:** Every LLM call makes future calls less likely. Facts and links accumulate,
coverage grows, hit rates increase. The cache doesn't just save money — it saves *more* money over time.

### Token Accounting

The admin dashboard tracks actual savings per query:

```
Query: "Compare DUI penalties in AZ vs CA"
  Intent: COMPARE (confidence: 0.97, tier: 1)
  Blocks retrieved: 2 sections, structured compression
  Context tokens: 160 (vs 2,400 full text = 93% reduction)
  LLM: haiku (structurer role)
  LLM output tokens: 340
  Total cost: $0.0004 (vs $0.012 traditional RAG = 97% savings)
  Assembly cached: yes (key: sha256:abc...)
```

### Chat ↔ Agent Bridge

Chat and agent modes share the same pipeline — they differ only in where they sit on the
intent spectrum:

- **Chat intents** (CITE, SUMMARIZE, COMPARE, EXPLAIN) → retrieval + assembly, cacheable
- **Hybrid intents** (THINK, ANALYZE, HYPOTHESIZE) → retrieval + reasoning, partially cacheable
- **Agent intents** (EXECUTE, BUILD, DEPLOY) → retrieval + tool-calling, plans cacheable

The input modality is abstracted: text, voice transcription, API call, messaging platform
message — all flow through the same intent detection → block resolution → assembly pipeline.

---

## Microservice Architecture

### Phase 1 — MVP (Chat + Caching Testing Ground)

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  Frontend   │────▶│   Gateway   │────▶│    Chat      │
│  (Next.js)  │     │  (FastAPI)  │     │  (FastAPI)   │
│  :3000      │     │  :8000      │     │  :8001       │
└─────────────┘     └──────┬──────┘     └──────┬───────┘
                           │                    │
                    ┌──────▼──────┐      ┌──────▼───────┐
                    │   Redis     │      │  PostgreSQL  │
                    │   :6379     │      │  + pgvector  │
                    │             │      │  :5432       │
                    └─────────────┘      └──────────────┘
```

**Embedded in Chat service:**
- Cache Engine (parameterized keying + double verify)
- Search Engine (BM25 + vector hybrid)
- LLM Router (any provider)
- Tool Layer (search_data, get_section)
- Gap Detector

### Phase 2 — Data Pipeline

Add: `ingest`, `embedder`, `monitor`, `invalidator`

### Phase 3 — Agent Execution

Add: `executor` (action plans, security, approvals, audit trail)

### Phase 4 — Advanced Caching

Add: `warmer` (predictive), `federation`, `review` (expert), `trainer` (model improvement)

### Phase 5 — API Partner Network

Add: `certifier`, `partner-portal`, revenue share tracking

---

## Data Schema (3-Tier + Cache)

### Tier 1: documents
Top-level containers. Any domain: legal, healthcare, financial, partner API data, etc.

### Tier 2: sections
Complete, coherent content units. Full text intact. BM25 search indexed.
SHA-256 version hash for change detection. Version history preserved.

### Tier 3: chunks
Paragraph-boundary splits for vector search (RAG) only.
384-dim embeddings via sentence-transformers.
Rendering always uses Tier 2 — chunks are retrieval-only.

### Tier 3b: blocks (NEW)
Pre-computed content at multiple compression levels per section.
Generated at ingestion time. Three compression tiers:
- **full** — complete source text (for reasoning/theorizing)
- **structured** — extracted key-value facts as JSON (for comparing/citing)
- **headline** — one-line summary (for listing/browsing)

Each block links to its parent section via section_id + version_hash.
When a section changes, all its blocks are invalidated and regenerated.
Blocks are the primary content unit consumed by the assembly engine —
the LLM never sees raw section text directly.

### Cache Tables

| Table | Purpose |
|-------|---------|
| `answer_cache` | Parameterized answers with source manifests |
| `content_blocks` | Pre-compressed content at full/structured/headline levels per section |
| `block_cache` | Maps section_id + compression_level → cached block content |
| `intent_log` | Query intent classifications with confidence scores and tier |
| `assembly_cache` | Assembled responses keyed by query + intent + filters + tenant |
| `tenants` | Multi-tenant registry with isolation config |
| `action_plans` | Agent execution plans with HMAC + approvals |
| `plan_executions` | Immutable audit trail of every plan execution |
| `change_events` | Source changes triggering invalidation |
| `source_monitors` | Polling config for external sources |
| `data_gaps` | Demand-driven acquisition queue |
| `answer_versions` | Version chains linking regenerated answers |
| `expert_reviews` | Domain expert corrections + confidence scores |
| `cache_metrics` | Serve counts, hit rates, generation costs, token accounting |
| `subscriptions` | User watch lists for change notifications |
| `query_embeddings` | Cached query vectors for semantic cache matching |

---

## Design Principles

1. **Library first, service second.** Every subsystem starts as a Python module in `bitmod-core`. It becomes a standalone service only when scale demands it.
2. **No message bus until needed.** Direct HTTP + shared DB first. NATS/Redis Streams when async workload demands it.
3. **Single database.** One PostgreSQL with logical separation. All cache tables, data tables, audit tables in one DB.
4. **LLM-agnostic.** Works with 200+ providers via universal OpenAI-compatible adapter, plus 12 native adapters. Cache the answer, not the model.
5. **Deploy anywhere.** Docker Compose on a laptop → Kubernetes in production → air-gapped on-prem. Same images, same code.
6. **Modular boundaries.** Each service owns its domain. Services communicate via well-defined APIs. Any service can be replaced without affecting others.
7. **Cache is the product.** Everything else is plumbing. The cache engine is the competitive moat protected by 49+ patent claims.
8. **Intent drives everything.** The system understands HOW the user wants to be answered, not just WHAT they're asking. Intent determines compression level, model tier, token budget, and cacheability.
9. **LLM does less, not more.** Facts come from verified data. The LLM only does work that requires intelligence (synthesis, reasoning, framing). Everything else is retrieval + assembly.
10. **Config over code.** New intents, roles, and model mappings are YAML config files. The system grows by adding config, not by modifying code.
11. **The system gets smarter by caching more, not by calling the LLM more.** Every LLM call produces artifacts (blocks, assemblies, plans) that make future calls unnecessary.

---

## Search Architecture

### Hybrid Search (BM25 + Vector)
- **BM25**: PostgreSQL tsvector full-text search on Tier 2 sections
- **Vector**: pgvector cosine similarity on Tier 3 chunks (384-dim)
- **Fusion**: Configurable weight blending (default 50/50), re-ranked by hybrid score
- **Abbreviation expansion**: "DUI" → "DUI driving under influence"
- **Jurisdiction filtering**: results scoped to user's contextual parameters

---

## Security Stack

| Layer | What It Does |
|-------|-------------|
| Content Security Policy | Locked to self, no external scripts |
| Rate Limiting | Configurable per-route (Redis-backed in production) |
| Input Sanitization | HTML escape, null byte removal, length limits |
| HMAC Plan Integrity | SHA-256 + HMAC on every cached action plan |
| Typed Parameter Validation | Regex + type constraints on injected parameters |
| Tool Scope Enforcement | Allowlist/denylist per plan, no privilege escalation |
| Execution Sandbox | Step outputs isolated, external calls via allowlist proxy |
| Scoped Approvals | Bound to plan hash + parameter constraints + expiry |
| Immutable Audit Trail | Every execution recorded: who, when, what, result |

---

## Domains

- **Website**: bitmod.io
- **API**: api.bitmod.io
- **Docs**: docs.bitmod.io

---

## Reference Documents

- Patent Draft: (private — not included in repo)
- Patent Diagrams: (private — not included in repo)
- Business Plan: (private — not included in repo)
