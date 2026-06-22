/**
 * Admin metrics data normalization layer.
 *
 * This module sits between the raw API response and the admin page component.
 * It normalizes every field with safe defaults so the page NEVER crashes,
 * regardless of what shape or missing fields the API returns.
 *
 * If the API changes a field name (e.g. "format" → "source_format"), fix it
 * HERE — not scattered across the page component.
 */

// ─── Normalized types (what the page component consumes) ─────────

export interface NormalizedCache {
  total_entries: number
  valid_entries: number
  invalidated_entries: number
  hit_rate: number
  total_compute_saved_s: number
  total_compute_saved_ms: number
  avg_generation_ms: number
  total_serves: number
  recent_queries: Array<{
    question: string
    generation_ms: number
    serve_count: number
    is_valid: boolean
    model_used: string
    created_at: string
  }>
}

export interface NormalizedDocument {
  title: string
  format: string
  sections: number
  chunks: number
  created_at: string
}

export interface NormalizedDocuments {
  documents: NormalizedDocument[]
  totals: {
    document_count: number
    total_sections: number
    total_chunks: number
  }
}

export interface NormalizedComparisonQuery {
  query: string
  first_gen_ms: number
  cached_serve_ms: number
  serves: number
  model_used: string
  total_without_cache_ms: number
  total_with_cache_ms: number
  savings_ms: number
  input_tokens: number
  output_tokens: number
  cost_per_call: number
  total_cost_without: number
  total_cost_with: number
  cost_saved: number
}

export interface NormalizedComparison {
  queries: NormalizedComparisonQuery[]
  total_without_ms: number
  total_with_ms: number
  savings_factor: number
  total_cost_without: number
  total_cost_with: number
  total_cost_saved: number
  total_tokens_without: number
  total_tokens_with: number
  pricing_updated: string
  pricing_stale: boolean
}

export interface NormalizedProviders {
  llm: Array<Record<string, unknown>>
  database: Array<Record<string, unknown>>
  embeddings: Array<Record<string, unknown>>
  vector_store: Array<Record<string, unknown>>
}

export interface NormalizedAccuracy {
  overall_score: number
  total_scored_batches: number
  batches: Array<{
    batch: number
    name: string
    accuracy: number
    relevance: number
    completeness: number
    coherence: number
    total: number
  }>
}

export interface NormalizedConversation {
  id: string
  project_id: string
  user_message: string
  assistant_response: string
  model_used: string
  cache_hit: boolean
  generation_ms: number
  rating: number | null
  created_at: string
}

export interface AdminMetrics {
  cache: NormalizedCache
  documents: NormalizedDocuments
  comparison: NormalizedComparison
  providers: NormalizedProviders
  accuracy: NormalizedAccuracy
  conversations: NormalizedConversation[]
}

// ─── Safe accessors ──────────────────────────────────────────────

function num(v: unknown, fallback = 0): number {
  if (typeof v === "number" && !isNaN(v)) return v
  if (typeof v === "string") {
    const n = parseFloat(v)
    if (!isNaN(n)) return n
  }
  return fallback
}

function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback
}

function bool(v: unknown, fallback = false): boolean {
  return typeof v === "boolean" ? v : fallback
}

function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : []
}

function obj(v: unknown): Record<string, unknown> {
  return v != null && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {}
}

// ─── Normalizers ─────────────────────────────────────────────────

function normalizeCache(raw: unknown): NormalizedCache {
  const c = obj(raw)
  return {
    total_entries: num(c.total_entries),
    valid_entries: num(c.valid_entries),
    invalidated_entries: num(c.invalidated_entries),
    hit_rate: num(c.hit_rate),
    total_compute_saved_s: num(c.total_compute_saved_s),
    total_compute_saved_ms: num(c.total_compute_saved_ms),
    avg_generation_ms: num(c.avg_generation_ms),
    total_serves: num(c.total_serves),
    recent_queries: arr(c.recent_queries).map((q) => {
      const qo = obj(q)
      return {
        question: str(qo.question, "Unknown query"),
        generation_ms: num(qo.generation_ms),
        serve_count: num(qo.serve_count),
        is_valid: bool(qo.is_valid, true),
        model_used: str(qo.model_used, "unknown"),
        created_at: str(qo.created_at),
      }
    }),
  }
}

function normalizeDocument(raw: unknown): NormalizedDocument {
  const d = obj(raw)
  return {
    // Accept either "format" or "source_format"
    title: str(d.title, "Untitled"),
    format: str(d.format || d.source_format, "text"),
    sections: num(d.sections ?? d.section_count),
    chunks: num(d.chunks ?? d.chunk_count),
    created_at: str(d.created_at),
  }
}

function normalizeDocuments(raw: unknown): NormalizedDocuments {
  const d = obj(raw)
  const docs = arr(d.documents).map(normalizeDocument)
  const totals = obj(d.totals)
  return {
    documents: docs,
    totals: {
      document_count: num(totals.document_count, docs.length),
      total_sections: num(totals.total_sections, docs.reduce((s, x) => s + x.sections, 0)),
      total_chunks: num(totals.total_chunks, docs.reduce((s, x) => s + x.chunks, 0)),
    },
  }
}

function normalizeComparisonQuery(raw: unknown): NormalizedComparisonQuery {
  const q = obj(raw)
  return {
    query: str(q.query, "Unknown query"),
    first_gen_ms: num(q.first_gen_ms),
    cached_serve_ms: num(q.cached_serve_ms, 0.5),
    serves: num(q.serves),
    model_used: str(q.model_used, "unknown"),
    total_without_cache_ms: num(q.total_without_cache_ms),
    total_with_cache_ms: num(q.total_with_cache_ms),
    savings_ms: num(q.savings_ms),
    input_tokens: num(q.input_tokens),
    output_tokens: num(q.output_tokens),
    cost_per_call: num(q.cost_per_call),
    total_cost_without: num(q.total_cost_without),
    total_cost_with: num(q.total_cost_with),
    cost_saved: num(q.cost_saved),
  }
}

function normalizeComparison(raw: unknown): NormalizedComparison {
  const c = obj(raw)
  const queries = arr(c.queries).map(normalizeComparisonQuery)

  // total_without / total_with may be a number or an object { total_ms, total_s }
  const tw = c.total_without
  const twMs = typeof tw === "number" ? tw : num(obj(tw).total_ms)
  const twi = c.total_with
  const twiMs = typeof twi === "number" ? twi : num(obj(twi).total_ms)

  return {
    queries,
    total_without_ms: twMs || queries.reduce((s, q) => s + q.total_without_cache_ms, 0),
    total_with_ms: twiMs || queries.reduce((s, q) => s + q.total_with_cache_ms, 0),
    savings_factor: num(c.savings_factor, 1),
    total_cost_without: num(c.total_cost_without),
    total_cost_with: num(c.total_cost_with),
    total_cost_saved: num(c.total_cost_saved),
    total_tokens_without: num(c.total_tokens_without),
    total_tokens_with: num(c.total_tokens_with),
    pricing_updated: str(c.pricing_updated),
    pricing_stale: bool(c.pricing_stale),
  }
}

function normalizeProviders(raw: unknown): NormalizedProviders {
  const p = obj(raw)
  return {
    llm: arr(p.llm).map((x) => obj(x)),
    database: arr(p.database).map((x) => obj(x)),
    embeddings: arr(p.embeddings).map((x) => obj(x)),
    vector_store: arr(p.vector_store).map((x) => obj(x)),
  }
}

function normalizeAccuracy(raw: unknown): NormalizedAccuracy {
  const a = obj(raw)
  return {
    overall_score: num(a.overall_score),
    total_scored_batches: num(a.total_scored_batches),
    batches: arr(a.batches).map((b) => {
      const bo = obj(b)
      return {
        batch: num(bo.batch),
        name: str(bo.name),
        accuracy: num(bo.accuracy),
        relevance: num(bo.relevance),
        completeness: num(bo.completeness),
        coherence: num(bo.coherence),
        total: num(bo.total),
      }
    }),
  }
}

// ─── Main entry point ────────────────────────────────────────────

/**
 * Normalize raw API JSON into a safe, typed AdminMetrics object.
 * Every field gets a safe default — the page will never crash from
 * missing or renamed API fields.
 */
function normalizeConversation(raw: unknown): NormalizedConversation {
  const c = obj(raw)
  return {
    id: str(c.id),
    project_id: str(c.project_id),
    user_message: str(c.user_message),
    assistant_response: str(c.assistant_response),
    model_used: str(c.model_used, "unknown"),
    cache_hit: bool(c.cache_hit),
    generation_ms: num(c.generation_ms),
    rating: c.rating != null ? num(c.rating) : null,
    created_at: str(c.created_at),
  }
}

export function normalizeMetrics(raw: unknown): AdminMetrics {
  const r = obj(raw)
  return {
    cache: normalizeCache(r.cache),
    documents: normalizeDocuments(r.documents),
    comparison: normalizeComparison(r.comparison),
    providers: normalizeProviders(r.providers),
    accuracy: normalizeAccuracy(r.accuracy),
    conversations: arr(r.conversations).map(normalizeConversation),
  }
}
