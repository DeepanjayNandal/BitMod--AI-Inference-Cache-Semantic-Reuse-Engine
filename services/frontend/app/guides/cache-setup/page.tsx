import type { Metadata } from "next"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { CodeBlock } from "@/components/shared/code-block"
import { ArrowRight, Clock, Terminal, Layers, Zap } from "lucide-react"

export const metadata: Metadata = {
  title: "Setting Up Your First Cache | Guides | BitMod",
  description: "Learn how BitMod's 9-layer cache engine works, configure TTLs, and monitor your cache hit rates.",
}

export default function CacheSetupGuide() {
  return (
    <div className="relative">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-primary/10 blur-[120px]" />
      </div>

      <article className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-4">
            <Badge variant="accent">Guide</Badge>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span>10 min read</span>
            </div>
            <Badge className="bg-green-500/15 text-green-400 border-green-500/30">Beginner</Badge>
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
            Setting Up Your First Cache
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Understand how the 9-layer cache engine works, configure TTLs for your workload, and monitor hit rates in real time.
          </p>
        </div>

        <div className="space-y-12">
          {/* The 9-Layer Pipeline */}
          <section>
            <h2 className="text-xl font-semibold mb-4">How the 9-Layer Cache Works</h2>
            <p className="text-muted-foreground mb-6">
              Every query passes through 9 cache layers in sequence. The first layer to return a match short-circuits the rest — no LLM call needed.
              Each layer targets a different type of redundancy:
            </p>

            <div className="space-y-3">
              {[
                { layer: 1, name: "Normalization", desc: "Normalizes query text (whitespace, casing, punctuation) to maximize downstream match rates." },
                { layer: 2, name: "Exact Cache Match", desc: "SHA-256 composite key lookup — byte-identical queries return instantly." },
                { layer: 3, name: "Double Verification", desc: "Validates source version hashes to ensure cached answers are still current." },
                { layer: 4, name: "TTL Expiration Check", desc: "Enforces time-to-live and freshness scoring before serving any cached entry." },
                { layer: 5, name: "Fuzzy Query Matching", desc: "Order-independent token matching for typos and minor variations in phrasing." },
                { layer: 6, name: "Semantic Cache Matching", desc: "Embedding similarity search — catches paraphrased queries above a cosine threshold." },
                { layer: 7, name: "Composable Query Decomposition", desc: "Decomposes multi-part queries into sub-queries that may already be cached independently." },
                { layer: 8, name: "Temporal Query Handling", desc: "Recognizes and routes historical or time-sensitive queries appropriately." },
                { layer: 9, name: "LRU Eviction", desc: "Least-recently-used eviction keeps the cache within configured size limits." },
              ].map(({ layer, name, desc }) => (
                <Card key={layer} className="border-border/40 bg-card/50">
                  <CardContent className="p-4 flex items-start gap-4">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary shrink-0">
                      {layer}
                    </div>
                    <div>
                      <p className="font-medium text-sm">{name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <p className="text-sm text-muted-foreground mt-4">
              After a cache hit, the <strong className="text-foreground">Cache Qualification Layer</strong> checks for context-dependent queries &mdash; follow-ups like &ldquo;tell me more&rdquo;, pronoun references, and short continuations that need conversation history. These are routed to the LLM with full context instead of being served from cache. The pipeline trace shows <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">SKIP_QUALIFIED(context_dependent)</code> when this happens.
            </p>

            <p className="text-sm text-muted-foreground mt-2">
              Every response includes a <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">pipeline_trace</code> showing which layers were checked and which one matched.
            </p>
          </section>

          {/* Configuring TTL */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Configuring Cache TTL</h2>
            <p className="text-muted-foreground mb-4">
              TTL (time-to-live) controls how long cached responses remain valid. Set it globally or per-layer in your <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">bitmod.yaml</code>:
            </p>

            <CodeBlock filename="bitmod.yaml">
{`# Flat config keys — BitMod does not use nested YAML structures
cache_default_ttl: 86400          # 24 hours (seconds)
cache_semantic_threshold: 0.88    # cosine similarity for semantic matching
cache_fuzzy_threshold: 0.85       # threshold for fuzzy token matching
cache_composable_threshold: 0.80  # threshold for composable sub-queries
cache_search_threshold: 0.75      # threshold for search matching
cache_max_entries: 100000         # maximum cache entries
cache_eviction_interval: 100      # evict every N inserts
cache_link_cleanup_days: 30       # remove stale similarity links`}
            </CodeBlock>

            <p className="text-sm text-muted-foreground mt-3 mb-4">Or set via environment variables (these override YAML):</p>

            <CodeBlock filename=".env">
{`BITMOD_CACHE_DEFAULT_TTL=86400
BITMOD_CACHE_SEMANTIC_THRESHOLD=0.88
BITMOD_CACHE_FUZZY_THRESHOLD=0.85
BITMOD_CACHE_COMPOSABLE_THRESHOLD=0.80
BITMOD_CACHE_SEARCH_THRESHOLD=0.75
BITMOD_CACHE_MAX_ENTRIES=100000
BITMOD_CACHE_EVICTION_INTERVAL=100
BITMOD_CACHE_LINK_CLEANUP_DAYS=30`}
            </CodeBlock>

            <p className="text-sm text-muted-foreground mt-4">
              Setting <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">cache_default_ttl: 0</code> means entries never expire (manual invalidation only).
            </p>
          </section>

          {/* Semantic similarity threshold */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Tuning Semantic Similarity</h2>
            <p className="text-muted-foreground mb-4">
              The semantic match layer uses vector embeddings to find paraphrased queries. The <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">similarity_threshold</code> controls
              how close two queries must be to count as a match:
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40">
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Threshold</th>
                    <th className="text-left py-2 pr-4 text-muted-foreground font-medium">Behavior</th>
                    <th className="text-left py-2 text-muted-foreground font-medium">Best For</th>
                  </tr>
                </thead>
                <tbody className="text-muted-foreground">
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">0.98</td>
                    <td className="py-2 pr-4">Very strict — near-identical phrasing only</td>
                    <td className="py-2">Medical, legal, compliance</td>
                  </tr>
                  <tr className="border-b border-border/20">
                    <td className="py-2 pr-4 font-mono text-primary/80">0.88</td>
                    <td className="py-2 pr-4">Balanced (default) — catches paraphrases</td>
                    <td className="py-2">General purpose</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 font-mono text-primary/80">0.85</td>
                    <td className="py-2 pr-4">Aggressive — higher hit rate, more false matches</td>
                    <td className="py-2">FAQ bots, support chat</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* Monitoring */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Monitoring Hit Rates</h2>
            <p className="text-muted-foreground mb-4">
              Check real-time cache performance through the API or the admin dashboard:
            </p>

            <CodeBlock filename="terminal">
{`curl http://localhost:8000/v1/admin/metrics

# {
#   "cache": {
#     "hit_rate": 72.4,
#     "total_entries": 1847,
#     "valid_entries": 1623,
#     "total_serves": 4291,
#     "avg_generation_ms": 1240,
#     "total_compute_saved_s": 3842
#   }
# }`}
            </CodeBlock>

            <p className="text-muted-foreground mt-4 mb-4">
              Each response also includes a <code className="text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono">pipeline_trace</code> header showing exactly which layers were checked:
            </p>

            <CodeBlock filename="response headers">
{`X-BitMod-Cache: HIT
X-BitMod-Layer: semantic_match
X-BitMod-Latency: 0.8ms
X-BitMod-Pipeline-Trace: normalization:PASS(0.1ms) > exact_cache_match:MISS(0.1ms) > double_verification:SKIP > ttl_check:SKIP > fuzzy_match:MISS(0.2ms) > semantic_match:HIT(0.5ms)`}
            </CodeBlock>
          </section>

          {/* Invalidation */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Cache Invalidation</h2>
            <p className="text-muted-foreground mb-4">
              Invalidate specific entries or flush the entire cache when your data changes:
            </p>

            <CodeBlock filename="terminal">
{`# Invalidate a specific cached query
curl -X DELETE http://localhost:8000/v1/cache \\
  -H "Content-Type: application/json" \\
  -d '{"query": "What is semantic caching?"}'

# Flush all cache entries
curl -X DELETE http://localhost:8000/v1/cache/all

# Invalidate by namespace
curl -X DELETE http://localhost:8000/v1/cache/namespace/production`}
            </CodeBlock>
          </section>

          {/* Summary */}
          <Card className="border-border/40 bg-card/50">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-primary/10 p-2">
                  <Layers className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-semibold mb-1">Key Takeaways</h3>
                  <ul className="text-sm text-muted-foreground space-y-1">
                    <li>The 9-layer pipeline catches redundant queries at multiple levels of similarity.</li>
                    <li>TTLs are configurable per-layer — use longer TTLs for exact matches, shorter for semantic.</li>
                    <li>Monitor via <code className="text-primary/80 bg-primary/10 px-1 py-0.5 rounded text-xs font-mono">/v1/admin/metrics</code> or the pipeline_trace headers.</li>
                    <li>A semantic similarity threshold of 0.88 is a good starting point for most workloads.</li>
                    <li>The Cache Qualification Layer detects context-dependent queries and routes them to the LLM — see the <a href="/cache-engine" className="text-primary hover:underline">cache engine page</a> for details.</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Next Steps */}
          <section>
            <h2 className="text-xl font-semibold mb-4">Next Steps</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Link href="/guides/llm-providers" className="group">
                <Card className="h-full border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300">
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="rounded-lg bg-primary/10 p-2 shrink-0">
                      <Terminal className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">Connecting Your LLM Provider</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Anthropic, OpenAI, Ollama, and more</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                  </CardContent>
                </Card>
              </Link>
              <Link href="/guides/getting-started" className="group">
                <Card className="h-full border-border/40 bg-card/50 hover:border-border/80 transition-all duration-300">
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="rounded-lg bg-primary/10 p-2 shrink-0">
                      <Zap className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">Getting Started with BitMod</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Install and send your first query</p>
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
