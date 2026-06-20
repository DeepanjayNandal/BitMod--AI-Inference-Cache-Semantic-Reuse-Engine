"""Tests for UsageTracker — cost tracking and usage analytics."""

import time
import pytest

from bitmod.usage import (
    UsageTracker,
    UsageRecord,
    UsageSummary,
    DailyUsage,
    estimate_cost,
)


# ---------------------------------------------------------------------------
# Mock backend with store_usage / get_usage
# ---------------------------------------------------------------------------

class MockUsageBackend:
    """In-memory backend that implements store_usage and get_usage."""

    def __init__(self):
        self._records: list[dict] = []

    class _Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def session(self):
        return self._Session()

    def store_usage(self, session, *, record_id, timestamp, query_hash,
                    model, provider, input_tokens, output_tokens, cached,
                    cache_layer, latency_ms, tenant_id,
                    estimated_cost_usd, estimated_savings_usd):
        self._records.append({
            "record_id": record_id,
            "timestamp": timestamp,
            "query_hash": query_hash,
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached": cached,
            "cache_layer": cache_layer,
            "latency_ms": latency_ms,
            "tenant_id": tenant_id,
            "estimated_cost_usd": estimated_cost_usd,
            "estimated_savings_usd": estimated_savings_usd,
        })

    def get_usage(self, session, *, tenant_id, since):
        return [r for r in self._records
                if r["tenant_id"] == tenant_id and r["timestamp"] >= since]


class NoUsageBackend:
    """Backend without store_usage/get_usage methods."""

    class _Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def session(self):
        return self._Session()


# ---------------------------------------------------------------------------
# Cost estimation tests
# ---------------------------------------------------------------------------

class TestEstimateCost:
    def test_known_model(self):
        # pricing.json: gpt-4o = (2.50, 10.00) per 1M tokens
        cost = estimate_cost("gpt-4o", input_tokens=1000, output_tokens=500)
        expected = 1000 * (2.50 / 1_000_000) + 500 * (10.00 / 1_000_000)
        assert abs(cost - expected) < 1e-6

    def test_anthropic_model(self):
        # pricing.json: claude-sonnet-4-6 = (3.00, 15.00) per 1M tokens
        cost = estimate_cost("claude-sonnet-4-6", input_tokens=2000, output_tokens=1000)
        expected = 2000 * (3.00 / 1_000_000) + 1000 * (15.00 / 1_000_000)
        assert abs(cost - expected) < 1e-6

    def test_unknown_model_uses_default(self):
        # pricing.json: _default = (0.50, 1.50) per 1M tokens
        cost = estimate_cost("some-unknown-model", input_tokens=1000, output_tokens=500)
        expected = 1000 * (0.50 / 1_000_000) + 500 * (1.50 / 1_000_000)
        assert abs(cost - expected) < 1e-6

    def test_zero_tokens(self):
        cost = estimate_cost("gpt-4o", input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_gemini_model(self):
        # pricing.json: gemini-2.0-flash = (0.10, 0.40) per 1M tokens
        cost = estimate_cost("gemini-2.0-flash", input_tokens=5000, output_tokens=2000)
        expected = 5000 * (0.10 / 1_000_000) + 2000 * (0.40 / 1_000_000)
        assert abs(cost - expected) < 1e-6


# ---------------------------------------------------------------------------
# UsageTracker.record tests
# ---------------------------------------------------------------------------

class TestUsageRecord:
    def test_record_cache_miss(self):
        backend = MockUsageBackend()
        tracker = UsageTracker(backend)

        record = UsageRecord(
            timestamp=time.time(),
            query_hash="abc123",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cached=False,
            cache_layer="miss",
            latency_ms=250.0,
        )
        tracker.record(record)

        assert len(backend._records) == 1
        stored = backend._records[0]
        assert stored["cached"] is False
        assert stored["estimated_cost_usd"] > 0
        assert stored["estimated_savings_usd"] == 0

    def test_record_cache_hit(self):
        backend = MockUsageBackend()
        tracker = UsageTracker(backend)

        record = UsageRecord(
            timestamp=time.time(),
            query_hash="def456",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cached=True,
            cache_layer="exact",
            latency_ms=2.0,
        )
        tracker.record(record)

        assert len(backend._records) == 1
        stored = backend._records[0]
        assert stored["cached"] is True
        assert stored["estimated_cost_usd"] == 0
        assert stored["estimated_savings_usd"] > 0

    def test_record_without_store_usage(self):
        """Backend without store_usage should not raise."""
        backend = NoUsageBackend()
        tracker = UsageTracker(backend)

        record = UsageRecord(
            timestamp=time.time(),
            query_hash="xyz",
            model="gpt-4o",
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            cached=False,
            cache_layer="miss",
            latency_ms=100.0,
        )
        # Should not raise
        tracker.record(record)


# ---------------------------------------------------------------------------
# UsageTracker.get_summary tests
# ---------------------------------------------------------------------------

class TestGetSummary:
    def _populate(self, backend, tracker, n_hits=3, n_misses=2):
        now = time.time()
        for i in range(n_hits):
            tracker.record(UsageRecord(
                timestamp=now - i * 60,
                query_hash=f"hit-{i}",
                model="gpt-4o",
                provider="openai",
                input_tokens=100,
                output_tokens=50,
                cached=True,
                cache_layer="exact",
                latency_ms=2.0,
            ))
        for i in range(n_misses):
            tracker.record(UsageRecord(
                timestamp=now - (n_hits + i) * 60,
                query_hash=f"miss-{i}",
                model="gpt-4o",
                provider="openai",
                input_tokens=200,
                output_tokens=100,
                cached=False,
                cache_layer="miss",
                latency_ms=300.0,
            ))

    def test_summary_calculations(self):
        backend = MockUsageBackend()
        tracker = UsageTracker(backend)
        self._populate(backend, tracker, n_hits=3, n_misses=2)

        summary = tracker.get_summary(tenant_id="default", days=30)
        assert summary.total_queries == 5
        assert summary.cache_hits == 3
        assert summary.cache_misses == 2
        assert summary.hit_rate_pct == 60.0
        assert summary.estimated_savings_usd > 0
        assert summary.estimated_cost_usd > 0
        assert len(summary.top_models) >= 1
        assert summary.top_models[0]["model"] == "gpt-4o"

    def test_summary_no_data(self):
        backend = MockUsageBackend()
        tracker = UsageTracker(backend)

        summary = tracker.get_summary(tenant_id="default", days=30)
        assert summary.total_queries == 0
        assert summary.hit_rate_pct == 0.0

    def test_summary_without_get_usage(self):
        backend = NoUsageBackend()
        tracker = UsageTracker(backend)

        summary = tracker.get_summary(tenant_id="default", days=30)
        assert summary.total_queries == 0


# ---------------------------------------------------------------------------
# UsageTracker.get_daily_breakdown tests
# ---------------------------------------------------------------------------

class TestDailyBreakdown:
    def test_daily_aggregation(self):
        backend = MockUsageBackend()
        tracker = UsageTracker(backend)
        now = time.time()

        # Add records spread across 2 days
        for i in range(3):
            tracker.record(UsageRecord(
                timestamp=now - i * 60,
                query_hash=f"today-{i}",
                model="gpt-4o",
                provider="openai",
                input_tokens=100,
                output_tokens=50,
                cached=i % 2 == 0,
                cache_layer="exact" if i % 2 == 0 else "miss",
                latency_ms=10.0,
            ))
        for i in range(2):
            tracker.record(UsageRecord(
                timestamp=now - 86400 - i * 60,
                query_hash=f"yesterday-{i}",
                model="claude-sonnet-4-6",
                provider="anthropic",
                input_tokens=200,
                output_tokens=100,
                cached=False,
                cache_layer="miss",
                latency_ms=200.0,
            ))

        breakdown = tracker.get_daily_breakdown(tenant_id="default", days=30)
        assert len(breakdown) == 2
        # Each entry should have the required fields
        for day in breakdown:
            assert isinstance(day.date, str)
            assert day.total_queries > 0

    def test_daily_breakdown_without_get_usage(self):
        backend = NoUsageBackend()
        tracker = UsageTracker(backend)

        breakdown = tracker.get_daily_breakdown(tenant_id="default", days=30)
        assert breakdown == []
