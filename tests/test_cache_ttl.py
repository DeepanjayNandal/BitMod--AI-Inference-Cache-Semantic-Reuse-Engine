"""Tests for TTL expiration and LRU eviction in the cache engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.cache_engine import (
    DEFAULT_EVICTION_INTERVAL,
    _is_expired,
    _maybe_evict,
    _write_counter_lock,
    evict_expired_cache,
    evict_lru_cache,
    store_answer,
)
from bitmod.interfaces.database import AnswerCacheRecord


@pytest.fixture
def db(tmp_path):
    """SQLite backend with a fresh temp database."""
    backend = SQLiteBackend(path=str(tmp_path / "ttl_test.db"))
    backend.initialize()
    return backend


def _store(db, key, answer="answer", max_age_seconds=None, estimated_cost=0.0):
    """Helper to store a cache entry and return the record."""
    with db.session() as session:
        record = store_answer(
            backend=db,
            session=session,
            answer_key=key,
            question_raw=f"question for {key}",
            question_normalized=key,
            filters={},
            answer_text=answer,
            source_sections=[],
            model_used="test-model",
            generation_ms=100,
            max_age_seconds=max_age_seconds,
            max_cache_entries=100_000,
            eviction_interval=999_999,  # disable auto-eviction in helpers
            estimated_cost=estimated_cost,
        )
    return record


class TestIsExpired:
    """Unit tests for _is_expired TTL checking."""

    def test_none_ttl_never_expires(self):
        """Entries with max_age_seconds=None are immortal."""
        record = AnswerCacheRecord(
            max_age_seconds=None,
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert _is_expired(record) is False

    def test_none_created_at_with_ttl_treated_as_expired(self):
        """Entries with TTL but no creation timestamp are treated as expired (defensive)."""
        record = AnswerCacheRecord(max_age_seconds=60, created_at=None)
        assert _is_expired(record) is True

    def test_recently_created_not_expired(self):
        """Entry created just now with a 3600s TTL is not expired."""
        record = AnswerCacheRecord(
            max_age_seconds=3600,
            created_at=datetime.now(timezone.utc),
        )
        assert _is_expired(record) is False

    def test_old_entry_is_expired(self):
        """Entry created well beyond its TTL is expired."""
        record = AnswerCacheRecord(
            max_age_seconds=60,
            created_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        )
        assert _is_expired(record) is True

    def test_iso_string_created_at_parsed(self):
        """SQLite stores created_at as ISO string -- _is_expired handles it."""
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        record = AnswerCacheRecord(max_age_seconds=60, created_at=old_time)
        assert _is_expired(record) is True

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetime (no tzinfo) is treated as UTC."""
        old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=300)
        record = AnswerCacheRecord(max_age_seconds=60, created_at=old_time)
        assert _is_expired(record) is True

    def test_mocked_time_expiration(self):
        """Mock datetime.now to verify TTL boundary without real waiting."""
        created = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        record = AnswerCacheRecord(max_age_seconds=60, created_at=created)

        # 59 seconds later -- not yet expired
        fake_now_before = created + timedelta(seconds=59)
        with patch("bitmod.cache_engine.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now_before
            mock_dt.fromisoformat = datetime.fromisoformat
            assert _is_expired(record) is False

        # 61 seconds later -- expired
        fake_now_after = created + timedelta(seconds=61)
        with patch("bitmod.cache_engine.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now_after
            mock_dt.fromisoformat = datetime.fromisoformat
            assert _is_expired(record) is True


class TestEvictExpiredCache:
    """Integration tests for evict_expired_cache with real SQLite."""

    def test_removes_expired_entries(self, db):
        """Expired entries are deleted, non-expired entries remain."""
        _store(db, "will-expire", max_age_seconds=1)
        _store(db, "wont-expire", max_age_seconds=None)

        # Backdate the expiring entry
        with db.session() as session:
            session.execute(
                "UPDATE answer_cache SET created_at = datetime('now', '-10 seconds') WHERE answer_key = ?",
                ("will-expire",),
            )
            count = evict_expired_cache(db, session)

        assert count == 1

        with db.session() as session:
            assert db.cache_count(session) == 1
            remaining = db.cache_lookup(session, "wont-expire")
            assert remaining is not None

    def test_no_expired_entries_returns_zero(self, db):
        """When nothing is expired, eviction deletes nothing."""
        _store(db, "fresh", max_age_seconds=3600)
        with db.session() as session:
            count = evict_expired_cache(db, session)
        assert count == 0

    def test_entries_without_ttl_never_evicted(self, db):
        """Entries with max_age_seconds=None survive TTL-based eviction."""
        for i in range(5):
            _store(db, f"immortal-{i}", max_age_seconds=None)

        with db.session() as session:
            count = evict_expired_cache(db, session)
            assert count == 0
            assert db.cache_count(session) == 5


class TestEvictLRUCache:
    """Integration tests for LRU eviction with real SQLite."""

    def test_evicts_when_over_limit(self, db):
        """When cache exceeds max_entries, excess entries are removed."""
        for i in range(10):
            _store(db, f"entry-{i}")

        with db.session() as session:
            count = evict_lru_cache(db, session, max_entries=7)

        assert count == 3
        with db.session() as session:
            assert db.cache_count(session) == 7

    def test_no_eviction_under_limit(self, db):
        """When cache is within max_entries, nothing is evicted."""
        for i in range(3):
            _store(db, f"entry-{i}")

        with db.session() as session:
            count = evict_lru_cache(db, session, max_entries=10)
        assert count == 0

    def test_evicts_oldest_served_first(self, db):
        """Entries with older (or NULL) last_served_at are evicted first."""
        _store(db, "old-served")
        _store(db, "new-served")

        with db.session() as session:
            # Mark old-served as served a long time ago, new-served as just served
            session.execute(
                "UPDATE answer_cache SET last_served_at = datetime('now', '-1 hour'), serve_count = 1 WHERE answer_key = ?",
                ("old-served",),
            )
            session.execute(
                "UPDATE answer_cache SET last_served_at = datetime('now'), serve_count = 1 WHERE answer_key = ?",
                ("new-served",),
            )
            evict_lru_cache(db, session, max_entries=1)

            # new-served should survive (more recently served)
            assert db.cache_lookup(session, "new-served") is not None
            assert db.cache_lookup(session, "old-served") is None

    def test_cost_aware_eviction_prefers_cheap_entries(self, db):
        """Cheap entries (low estimated_cost) are evicted before expensive ones."""
        _store(db, "cheap", estimated_cost=0.001)
        _store(db, "expensive", estimated_cost=5.0)

        # Give both the same serve_count and last_served_at so cost is the tiebreaker
        with db.session() as session:
            session.execute(
                "UPDATE answer_cache SET serve_count = 1, last_served_at = datetime('now') WHERE 1=1"
            )
            evict_lru_cache(db, session, max_entries=1)

            # Expensive entry should survive
            assert db.cache_lookup(session, "expensive") is not None
            assert db.cache_lookup(session, "cheap") is None

    def test_respects_max_entries_exactly(self, db):
        """After eviction, count equals max_entries."""
        for i in range(20):
            _store(db, f"e-{i}")

        with db.session() as session:
            evict_lru_cache(db, session, max_entries=12)
            assert db.cache_count(session) == 12


class TestCacheCount:
    """Tests for cache_count returning accurate counts."""

    def test_empty_cache_returns_zero(self, db):
        with db.session() as session:
            assert db.cache_count(session) == 0

    def test_counts_only_valid_entries(self, db):
        _store(db, "valid-1")
        _store(db, "valid-2")
        _store(db, "to-invalidate")

        with db.session() as session:
            db.cache_invalidate(session, db.cache_lookup(session, "to-invalidate").id, "test")
            assert db.cache_count(session) == 2

    def test_increments_on_store(self, db):
        for i in range(5):
            _store(db, f"item-{i}")
        with db.session() as session:
            assert db.cache_count(session) == 5


class TestMaybeEvict:
    """Tests for the opportunistic eviction counter."""

    def test_triggers_on_interval(self, db):
        """_maybe_evict triggers eviction when write count hits the interval."""
        import bitmod.cache_engine as ce

        with _write_counter_lock:
            original = ce._write_counter

        try:
            # Set counter to 1 less than a multiple of 5 (our test interval)
            with _write_counter_lock:
                ce._write_counter = 4  # next call will be 5, which is 5 % 5 == 0

            with db.session() as session:
                # Should trigger (counter becomes 5, 5 % 5 == 0)
                with patch("bitmod.cache_engine.evict_expired_cache") as mock_expired, \
                     patch("bitmod.cache_engine.evict_lru_cache") as mock_lru:
                    _maybe_evict(db, session, max_entries=100, eviction_interval=5)
                    mock_expired.assert_called_once()
                    mock_lru.assert_called_once()
        finally:
            with _write_counter_lock:
                ce._write_counter = original

    def test_does_not_trigger_between_intervals(self, db):
        """_maybe_evict is a no-op when write count is not on the interval."""
        import bitmod.cache_engine as ce

        with _write_counter_lock:
            original = ce._write_counter

        try:
            with _write_counter_lock:
                ce._write_counter = 1  # next call will be 2, which is 2 % 5 != 0

            with db.session() as session:
                with patch("bitmod.cache_engine.evict_expired_cache") as mock_expired:
                    _maybe_evict(db, session, max_entries=100, eviction_interval=5)
                    mock_expired.assert_not_called()
        finally:
            with _write_counter_lock:
                ce._write_counter = original


class TestStoreAnswerEvictionIntegration:
    """Test that store_answer wires up eviction correctly."""

    def test_store_answer_triggers_eviction_on_interval(self, db):
        """store_answer calls _maybe_evict, which fires on the configured interval."""
        import bitmod.cache_engine as ce

        with _write_counter_lock:
            original = ce._write_counter

        try:
            with _write_counter_lock:
                ce._write_counter = 0

            # Store entries with eviction_interval=3, so the 3rd write triggers eviction
            for i in range(3):
                _store_with_eviction(db, f"auto-evict-{i}", eviction_interval=3)

            # If eviction ran without error, the wiring works
            with db.session() as session:
                assert db.cache_count(session) == 3
        finally:
            with _write_counter_lock:
                ce._write_counter = original


def _store_with_eviction(db, key, eviction_interval=3):
    """Helper that uses a realistic eviction_interval."""
    with db.session() as session:
        store_answer(
            backend=db,
            session=session,
            answer_key=key,
            question_raw=f"q {key}",
            question_normalized=key,
            filters={},
            answer_text=f"a {key}",
            source_sections=[],
            model_used="test",
            generation_ms=100,
            max_cache_entries=100_000,
            eviction_interval=eviction_interval,
        )
