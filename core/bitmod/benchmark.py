"""Cache benchmark framework for measuring pipeline effectiveness.

Runs a corpus of queries through the cache engine and produces a report
with hit rates, token savings, cost estimates, and latency percentiles.
Works entirely offline against the cache engine functions -- no running
server required.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field

from bitmod.cache_engine import (
    CacheEvidence,
    PipelineEvidence,
    _similarity_to_confidence,
    decompose_query,
    semantic_cache_search,
    try_cache,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Outcome of running a single query through the cache pipeline."""

    query: str
    query_type: str  # "repeated", "paraphrased", "decomposable", "unique"
    decision: str  # "SERVE", "GENERATE_WITH_CONTEXT", "GENERATE"
    cache_hit: bool
    layers_contributed: list[str]
    total_confidence: float
    input_tokens: int
    output_tokens: int
    latency_ms: float


@dataclass
class BenchmarkReport:
    """Aggregated benchmark results."""

    total_queries: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    hits_by_layer: dict[str, int] = field(default_factory=dict)
    hits_by_type: dict[str, int] = field(default_factory=dict)
    total_by_type: dict[str, int] = field(default_factory=dict)
    token_savings_pct: float = 0.0
    cost_savings_usd: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    results: list[QueryResult] = field(default_factory=list)

    def ascii_table(self) -> str:
        """Render the report as a human-readable ASCII table."""
        lines = [
            "",
            "=" * 60,
            "  BITMOD CACHE BENCHMARK REPORT",
            "=" * 60,
            f"  Total queries:       {self.total_queries}",
            f"  Cache hits:          {self.cache_hits}",
            f"  Cache hit rate:      {self.cache_hit_rate:.1%}",
            f"  Token savings:       {self.token_savings_pct:.1%}",
            f"  Cost savings (USD):  ${self.cost_savings_usd:.2f}",
            "-" * 60,
            "  LATENCY",
            f"    avg:  {self.avg_latency_ms:.2f} ms",
            f"    p50:  {self.p50_latency_ms:.2f} ms",
            f"    p95:  {self.p95_latency_ms:.2f} ms",
            f"    p99:  {self.p99_latency_ms:.2f} ms",
            "-" * 60,
            "  HITS BY LAYER",
        ]
        for layer, count in sorted(self.hits_by_layer.items(), key=lambda x: -x[1]):
            lines.append(f"    {layer:<20s} {count:>5d}")

        lines.append("-" * 60)
        lines.append("  HITS BY QUERY TYPE")
        for qtype in sorted(self.total_by_type.keys()):
            total = self.total_by_type[qtype]
            hits = self.hits_by_type.get(qtype, 0)
            rate = hits / total if total else 0
            lines.append(f"    {qtype:<20s} {hits:>3d}/{total:<3d} ({rate:.0%})")

        lines.append("=" * 60)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize report to JSON (excludes per-query results for brevity)."""
        return json.dumps(
            {
                "total_queries": self.total_queries,
                "cache_hits": self.cache_hits,
                "cache_hit_rate": self.cache_hit_rate,
                "hits_by_layer": self.hits_by_layer,
                "hits_by_type": self.hits_by_type,
                "total_by_type": self.total_by_type,
                "token_savings_pct": self.token_savings_pct,
                "cost_savings_usd": self.cost_savings_usd,
                "avg_latency_ms": self.avg_latency_ms,
                "p50_latency_ms": self.p50_latency_ms,
                "p95_latency_ms": self.p95_latency_ms,
                "p99_latency_ms": self.p99_latency_ms,
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------

# Claude Sonnet pricing (per 1K tokens)
_INPUT_COST_PER_1K = 0.003
_OUTPUT_COST_PER_1K = 0.015
_AVG_INPUT_TOKENS = 500
_AVG_OUTPUT_TOKENS = 300


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000) * _INPUT_COST_PER_1K + (output_tokens / 1000) * _OUTPUT_COST_PER_1K


# ---------------------------------------------------------------------------
# Paraphrase generation
# ---------------------------------------------------------------------------

_PARAPHRASE_TEMPLATES = [
    "Tell me about {topic}",
    "Explain {topic}",
    "What can you tell me about {topic}",
    "I want to understand {topic}",
    "Give me details on {topic}",
    "Could you describe {topic}",
    "Help me understand {topic}",
    "What do I need to know about {topic}",
]


def _paraphrase(query: str) -> str:
    """Generate a simple paraphrase of a query."""
    # Strip question marks and leading question words
    topic = query.rstrip("?").strip()
    for prefix in ("What is ", "What are ", "How does ", "Explain ", "Describe "):
        if topic.lower().startswith(prefix.lower()):
            topic = topic[len(prefix) :]
            break
    template = random.choice(_PARAPHRASE_TEMPLATES)  # noqa: S311 — benchmark corpus generation, not crypto
    return template.format(topic=topic)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


class CacheBenchmark:
    """Run a corpus of queries through the cache pipeline and measure results.

    Args:
        backend: A DatabaseBackend instance (e.g. SQLiteBackend).
        cache_engine_func: A callable(backend, session, query, filters) that runs
            the full cache pipeline and returns (PipelineEvidence, decision).
            If None, a default implementation using try_cache is used.
        corpus: List of dicts with keys "query" and "type".
        embedder: Optional embedder for semantic search. If None, semantic
            layer is skipped.
    """

    def __init__(
        self,
        backend,
        cache_engine_func=None,
        corpus: list[dict] | None = None,
        *,
        embedder=None,
    ):
        self._backend = backend
        self._cache_fn = cache_engine_func or self._default_cache_fn
        self._corpus = corpus or []
        self._embedder = embedder

    def _default_cache_fn(self, backend, session, query, filters):
        """Default pipeline: try exact cache, then semantic, then decompose."""
        evidence = PipelineEvidence()

        # Layer 1: exact cache
        cached = try_cache(backend, session, query, filters)
        if cached:
            evidence.add(
                CacheEvidence(
                    layer="exact",
                    confidence=0.99,
                    answer_text=cached.answer_text,
                    record_id=cached.id,
                )
            )

        # Layer 2: semantic (if embedder available)
        if self._embedder and evidence.total_confidence < 0.90:
            matches = semantic_cache_search(
                backend,
                session,
                query,
                filters,
                self._embedder,
                threshold=0.75,
                max_results=3,
            )
            for m in matches:
                conf = _similarity_to_confidence(m.similarity, "semantic")
                evidence.add(
                    CacheEvidence(
                        layer="semantic",
                        confidence=conf,
                        answer_text=m.record.answer_text,
                        record_id=m.record.id,
                        similarity=m.similarity,
                    )
                )

        # Layer 3: decomposable
        if evidence.total_confidence < 0.90:
            subs = decompose_query(query, filters)
            if subs:
                for sq in subs:
                    sub_cached = try_cache(backend, session, sq.query, sq.filters)
                    if sub_cached:
                        evidence.add(
                            CacheEvidence(
                                layer="composable",
                                confidence=0.70,
                                answer_text=sub_cached.answer_text,
                                record_id=sub_cached.id,
                                is_partial=True,
                                sub_query=sq.query,
                            )
                        )

        # Decision
        if evidence.total_confidence >= 0.90:
            decision = "SERVE"
        elif evidence.total_confidence >= 0.40:
            decision = "GENERATE_WITH_CONTEXT"
        else:
            decision = "GENERATE"
        evidence.decision = decision

        return evidence, decision

    def run(self) -> BenchmarkReport:
        """Execute the benchmark and produce a report."""
        results: list[QueryResult] = []

        with self._backend.session() as session:
            for entry in self._corpus:
                query = entry["query"]
                qtype = entry.get("type", "unique")
                filters = entry.get("filters")

                start = time.perf_counter()
                evidence, decision = self._cache_fn(self._backend, session, query, filters)
                elapsed_ms = (time.perf_counter() - start) * 1000

                cache_hit = decision == "SERVE"
                layers = [e.layer for e in evidence.evidences] if hasattr(evidence, "evidences") else []

                input_tokens = 0 if cache_hit else _AVG_INPUT_TOKENS
                output_tokens = 0 if cache_hit else _AVG_OUTPUT_TOKENS

                results.append(
                    QueryResult(
                        query=query,
                        query_type=qtype,
                        decision=decision,
                        cache_hit=cache_hit,
                        layers_contributed=layers,
                        total_confidence=evidence.total_confidence if hasattr(evidence, "total_confidence") else 0.0,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=elapsed_ms,
                    )
                )

        return self._build_report(results)

    def _build_report(self, results: list[QueryResult]) -> BenchmarkReport:
        report = BenchmarkReport()
        report.results = results
        report.total_queries = len(results)
        report.cache_hits = sum(1 for r in results if r.cache_hit)
        report.cache_hit_rate = report.cache_hits / report.total_queries if report.total_queries else 0.0

        # Hits by layer
        for r in results:
            for layer in r.layers_contributed:
                report.hits_by_layer[layer] = report.hits_by_layer.get(layer, 0) + 1

        # Hits by type
        for r in results:
            report.total_by_type[r.query_type] = report.total_by_type.get(r.query_type, 0) + 1
            if r.cache_hit:
                report.hits_by_type[r.query_type] = report.hits_by_type.get(r.query_type, 0) + 1

        # Token savings
        total_tokens_no_cache = report.total_queries * (_AVG_INPUT_TOKENS + _AVG_OUTPUT_TOKENS)
        actual_tokens = sum(r.input_tokens + r.output_tokens for r in results)
        report.token_savings_pct = (
            (total_tokens_no_cache - actual_tokens) / total_tokens_no_cache if total_tokens_no_cache > 0 else 0.0
        )

        # Cost savings
        cost_no_cache = sum(_estimate_cost(_AVG_INPUT_TOKENS, _AVG_OUTPUT_TOKENS) for _ in results)
        cost_actual = sum(_estimate_cost(r.input_tokens, r.output_tokens) for r in results)
        report.cost_savings_usd = cost_no_cache - cost_actual

        # Latency percentiles
        latencies = sorted(r.latency_ms for r in results)
        if latencies:
            report.avg_latency_ms = sum(latencies) / len(latencies)
            report.p50_latency_ms = _percentile(latencies, 50)
            report.p95_latency_ms = _percentile(latencies, 95)
            report.p99_latency_ms = _percentile(latencies, 99)

        return report

    @staticmethod
    def generate_corpus(
        base_queries: list[str],
        total: int = 200,
        *,
        repeated_pct: float = 0.30,
        paraphrased_pct: float = 0.20,
        decomposable_pct: float = 0.15,
        unique_pct: float = 0.35,
    ) -> list[dict]:
        """Generate a realistic benchmark corpus from base queries.

        Args:
            base_queries: Seed queries to build from.
            total: Total corpus size.
            repeated_pct: Fraction that are exact repeats of base queries.
            paraphrased_pct: Fraction that are paraphrased base queries.
            decomposable_pct: Fraction that are multi-part comparison queries.
            unique_pct: Fraction that are unique (never-seen) queries.

        Returns:
            List of dicts with "query" and "type" keys.
        """
        if not base_queries:
            return []

        n_repeated = int(total * repeated_pct)
        n_paraphrased = int(total * paraphrased_pct)
        n_decomposable = int(total * decomposable_pct)
        n_unique = total - n_repeated - n_paraphrased - n_decomposable

        corpus: list[dict] = []

        # Repeated: exact copies of base queries
        for _ in range(n_repeated):
            q = random.choice(base_queries)  # noqa: S311
            corpus.append({"query": q, "type": "repeated"})

        # Paraphrased: reworked versions
        for _ in range(n_paraphrased):
            q = random.choice(base_queries)  # noqa: S311
            corpus.append({"query": _paraphrase(q), "type": "paraphrased"})

        # Decomposable: "X vs Y" style comparisons
        for _ in range(n_decomposable):
            if len(base_queries) >= 2:
                a, b = random.sample(base_queries, 2)
                corpus.append({"query": f"{a} vs {b}", "type": "decomposable"})
            else:
                corpus.append({"query": base_queries[0], "type": "decomposable"})

        # Unique: queries with a unique suffix
        for i in range(n_unique):
            q = f"Unique question #{i}: {random.choice(base_queries)} with extra context"  # noqa: S311
            corpus.append({"query": q, "type": "unique"})

        random.shuffle(corpus)
        return corpus


def _percentile(sorted_values: list[float], pct: int) -> float:
    """Compute the pct-th percentile from a sorted list."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])
