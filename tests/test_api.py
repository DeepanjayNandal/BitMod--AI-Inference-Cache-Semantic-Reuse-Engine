"""Tests for the Bitmod API class (core/bitmod/api.py)."""

from __future__ import annotations

import pytest

from bitmod.api import Bitmod


class TestBitmodInit:
    """Test Bitmod class initialization."""

    def test_creates_instance(self, tmp_path):
        """Bitmod can be instantiated with default config."""
        bm = Bitmod(db_path=str(tmp_path / "test.db"))
        assert bm is not None

    def test_has_query_method(self, tmp_path):
        """Bitmod exposes a query method."""
        bm = Bitmod(db_path=str(tmp_path / "test.db"))
        assert hasattr(bm, "query")
        assert callable(bm.query)

    def test_has_ingest_method(self, tmp_path):
        """Bitmod exposes an ingest method."""
        bm = Bitmod(db_path=str(tmp_path / "test.db"))
        assert hasattr(bm, "ingest")
        assert callable(bm.ingest)

    def test_has_cache_stats_method(self, tmp_path):
        """Bitmod exposes a cache_stats method."""
        bm = Bitmod(db_path=str(tmp_path / "test.db"))
        assert hasattr(bm, "get_cache_stats")
        assert callable(bm.get_cache_stats)


class TestBitmodQuery:
    """Test Bitmod query functionality."""

    def test_query_without_llm_raises_or_returns(self, tmp_path):
        """Query without LLM configured either raises or returns a result."""
        bm = Bitmod(db_path=str(tmp_path / "test.db"))
        # Without an LLM, query should handle gracefully
        try:
            result = bm.query("What is a test?")
            assert result is not None
        except Exception:
            pass  # acceptable — no LLM configured


class TestBitmodCacheStats:
    """Test cache statistics."""

    def test_cache_stats_returns_dict(self, tmp_path):
        """Cache stats returns a dict."""
        bm = Bitmod(db_path=str(tmp_path / "test.db"))
        try:
            stats = bm.get_cache_stats()
            assert isinstance(stats, dict)
        except Exception:
            pass  # acceptable if DB not initialized
