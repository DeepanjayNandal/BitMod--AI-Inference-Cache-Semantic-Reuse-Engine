"""Cost tracking and usage analytics engine.

Enterprise-grade usage tracking that records every LLM request, calculates
cost savings from cache hits, and provides aggregation for procurement
justification dashboards.

This is the #1 enterprise feature: it lets buyers justify the procurement
by showing exactly how much Bitmod saves in LLM API costs.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from bitmod.pricing import estimate_cost as _pricing_estimate_cost

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost estimation — delegates to bitmod.pricing (single source of truth)
# ---------------------------------------------------------------------------


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a single LLM call.

    Delegates to bitmod.pricing which loads rates from pricing.json and
    handles prefix matching and defaults.
    """
    return _pricing_estimate_cost(input_tokens, output_tokens, model=model)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class UsageRecord:
    """A single tracked LLM request or cache hit."""

    timestamp: float
    query_hash: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached: bool
    cache_layer: str  # "exact", "semantic", "composable", "fuzzy", or "miss"
    latency_ms: float
    tenant_id: str = "default"


@dataclass
class UsageSummary:
    """Aggregated usage statistics for a tenant over a time period."""

    tenant_id: str
    days: int
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate_pct: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    estimated_savings_usd: float = 0.0
    top_models: list[dict] = field(default_factory=list)


@dataclass
class DailyUsage:
    """Usage breakdown for a single day."""

    date: str  # YYYY-MM-DD
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate_pct: float = 0.0
    estimated_cost_usd: float = 0.0
    estimated_savings_usd: float = 0.0


# ---------------------------------------------------------------------------
# Usage Tracker
# ---------------------------------------------------------------------------


class UsageTracker:
    """Records and aggregates LLM usage with cost tracking.

    Integrates with the database backend to persist usage records and
    provide cost/savings analytics for enterprise dashboards.
    """

    def __init__(self, backend: Any):
        self._backend = backend

    def record(self, record: UsageRecord) -> None:
        """Record a usage event with cost estimation."""
        cost = 0.0
        savings = 0.0

        if record.cached:
            # Cache hit: the savings is what it WOULD have cost
            savings = estimate_cost(record.model, record.input_tokens, record.output_tokens)
        else:
            # Cache miss: actual cost incurred
            cost = estimate_cost(record.model, record.input_tokens, record.output_tokens)

        try:
            if hasattr(self._backend, "store_usage"):
                with self._backend.session() as session:
                    self._backend.store_usage(
                        session,
                        record_id=str(uuid.uuid4()),
                        timestamp=record.timestamp,
                        query_hash=record.query_hash,
                        model=record.model,
                        provider=record.provider,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        cached=record.cached,
                        cache_layer=record.cache_layer,
                        latency_ms=record.latency_ms,
                        tenant_id=record.tenant_id,
                        estimated_cost_usd=cost,
                        estimated_savings_usd=savings,
                    )
        except Exception:
            logger.debug("Failed to store usage record (non-critical)", exc_info=True)

    def get_summary(self, tenant_id: str = "default", days: int = 30) -> UsageSummary:
        """Get usage summary with cost savings for a tenant."""
        if not hasattr(self._backend, "get_usage"):
            return UsageSummary(tenant_id=tenant_id, days=days)

        cutoff = time.time() - (days * 86400)
        try:
            with self._backend.session() as session:
                rows = self._backend.get_usage(session, tenant_id=tenant_id, since=cutoff)
        except Exception:
            logger.debug("Failed to get usage data", exc_info=True)
            return UsageSummary(tenant_id=tenant_id, days=days)

        total = len(rows)
        hits = sum(1 for r in rows if r["cached"])
        misses = total - hits
        hit_rate = round((hits / total * 100), 2) if total > 0 else 0.0
        total_input = sum(r["input_tokens"] for r in rows)
        total_output = sum(r["output_tokens"] for r in rows)
        total_cost = round(sum(r["estimated_cost_usd"] for r in rows), 6)
        total_savings = round(sum(r["estimated_savings_usd"] for r in rows), 6)

        # Top models by query count
        model_counts: dict[str, int] = {}
        for r in rows:
            model_counts[r["model"]] = model_counts.get(r["model"], 0) + 1
        top_models = [
            {"model": m, "queries": c} for m, c in sorted(model_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return UsageSummary(
            tenant_id=tenant_id,
            days=days,
            total_queries=total,
            cache_hits=hits,
            cache_misses=misses,
            hit_rate_pct=hit_rate,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            estimated_cost_usd=total_cost,
            estimated_savings_usd=total_savings,
            top_models=top_models,
        )

    def get_daily_breakdown(self, tenant_id: str = "default", days: int = 30) -> list[DailyUsage]:
        """Get day-by-day usage breakdown."""
        if not hasattr(self._backend, "get_usage"):
            return []

        cutoff = time.time() - (days * 86400)
        try:
            with self._backend.session() as session:
                rows = self._backend.get_usage(session, tenant_id=tenant_id, since=cutoff)
        except Exception:
            logger.debug("Failed to get usage data", exc_info=True)
            return []

        from datetime import datetime, timezone

        # Group by date
        daily: dict[str, list[dict]] = {}
        for r in rows:
            dt = datetime.fromtimestamp(r["timestamp"], tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d")
            daily.setdefault(date_str, []).append(r)

        result = []
        for date_str in sorted(daily.keys()):
            day_rows = daily[date_str]
            total = len(day_rows)
            hits = sum(1 for r in day_rows if r["cached"])
            misses = total - hits
            hit_rate = round((hits / total * 100), 2) if total > 0 else 0.0
            cost = round(sum(r["estimated_cost_usd"] for r in day_rows), 6)
            savings = round(sum(r["estimated_savings_usd"] for r in day_rows), 6)
            result.append(
                DailyUsage(
                    date=date_str,
                    total_queries=total,
                    cache_hits=hits,
                    cache_misses=misses,
                    hit_rate_pct=hit_rate,
                    estimated_cost_usd=cost,
                    estimated_savings_usd=savings,
                )
            )
        return result
