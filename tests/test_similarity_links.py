"""Tests for similarity link storage and retrieval via SQLiteBackend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.interfaces.database import SimilarityLink


@pytest.fixture
def db(tmp_path):
    """Initialized SQLiteBackend on a temp database."""
    backend = SQLiteBackend(path=str(tmp_path / "sim_test.db"))
    backend.initialize()
    return backend


def _make_link(
    *,
    id: str = "link-1",
    source: str = "cache-A",
    target: str = "cache-B",
    similarity: float = 0.92,
    strength: int = 0,
) -> SimilarityLink:
    return SimilarityLink(
        id=id,
        source_cache_id=source,
        target_cache_id=target,
        similarity=similarity,
        source_query_norm="query a",
        target_query_norm="query b",
        strength=strength,
    )


class TestSimilarityLinks:
    """Tests for similarity link CRUD operations."""

    def test_store_and_retrieve(self, db):
        """Store a link and retrieve it by source_cache_id."""
        link = _make_link()
        with db.session() as s:
            db.store_similarity_link(s, link)
        with db.session() as s:
            results = db.get_similarity_links(s, "cache-A")
        assert len(results) == 1
        assert results[0].id == "link-1"
        assert results[0].source_cache_id == "cache-A"
        assert results[0].target_cache_id == "cache-B"
        assert results[0].similarity == pytest.approx(0.92)
        assert results[0].strength == 0

    def test_get_similarity_links_returns_only_source_matches(self, db):
        """get_similarity_links only returns links originating from the given cache_id."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="l1", source="A", target="B"))
            db.store_similarity_link(s, _make_link(id="l2", source="C", target="A"))
        with db.session() as s:
            results = db.get_similarity_links(s, "A")
        assert len(results) == 1
        assert results[0].source_cache_id == "A"

    def test_get_similarity_links_targeting_returns_reverse(self, db):
        """get_similarity_links_targeting returns links where cache_id is the target."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="l1", source="A", target="B"))
            db.store_similarity_link(s, _make_link(id="l2", source="C", target="B"))
            db.store_similarity_link(s, _make_link(id="l3", source="B", target="D"))
        with db.session() as s:
            results = db.get_similarity_links_targeting(s, "B")
        assert len(results) == 2
        ids = {r.source_cache_id for r in results}
        assert ids == {"A", "C"}

    def test_increment_strength(self, db):
        """increment_similarity_link_strength increases counter by 1."""
        link = _make_link(strength=0)
        with db.session() as s:
            db.store_similarity_link(s, link)
            db.increment_similarity_link_strength(s, "link-1")
            db.increment_similarity_link_strength(s, "link-1")
        with db.session() as s:
            results = db.get_similarity_links(s, "cache-A")
        assert results[0].strength == 2

    def test_cleanup_weak_links_removes_old_zero_strength(self, db):
        """cleanup_weak_links removes links with strength=0 older than max_age_days."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="old-weak", strength=0))
            # Backdate the created_at to 60 days ago
            s.execute(
                "UPDATE similarity_links SET created_at = datetime('now', '-60 days') WHERE id = ?",
                ("old-weak",),
            )
        with db.session() as s:
            removed = db.cleanup_weak_links(s, max_age_days=30)
        assert removed == 1
        with db.session() as s:
            results = db.get_similarity_links(s, "cache-A")
        assert len(results) == 0

    def test_cleanup_weak_links_keeps_strong_links(self, db):
        """cleanup_weak_links preserves links with strength > 0 even if old."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="old-strong", strength=3))
            s.execute(
                "UPDATE similarity_links SET created_at = datetime('now', '-60 days') WHERE id = ?",
                ("old-strong",),
            )
        with db.session() as s:
            removed = db.cleanup_weak_links(s, max_age_days=30)
        assert removed == 0
        with db.session() as s:
            results = db.get_similarity_links(s, "cache-A")
        assert len(results) == 1

    def test_cleanup_weak_links_keeps_recent_zero_strength(self, db):
        """cleanup_weak_links keeps zero-strength links that are recent."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="new-weak", strength=0))
        with db.session() as s:
            removed = db.cleanup_weak_links(s, max_age_days=30)
        assert removed == 0

    def test_multiple_links_sorted_by_similarity_descending(self, db):
        """Results are ordered by similarity descending."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="l1", source="X", target="A", similarity=0.70))
            db.store_similarity_link(s, _make_link(id="l2", source="X", target="B", similarity=0.95))
            db.store_similarity_link(s, _make_link(id="l3", source="X", target="C", similarity=0.85))
        with db.session() as s:
            results = db.get_similarity_links(s, "X")
        sims = [r.similarity for r in results]
        assert sims == sorted(sims, reverse=True)
        assert sims[0] == pytest.approx(0.95)

    def test_limit_parameter(self, db):
        """Limit parameter restricts number of results returned."""
        with db.session() as s:
            for i in range(10):
                db.store_similarity_link(
                    s,
                    _make_link(id=f"l{i}", source="X", target=f"T{i}", similarity=0.5 + i * 0.01),
                )
        with db.session() as s:
            results = db.get_similarity_links(s, "X", limit=3)
        assert len(results) == 3

    def test_no_links_returns_empty(self, db):
        """Querying non-existent cache_id returns empty list."""
        with db.session() as s:
            results = db.get_similarity_links(s, "nonexistent")
        assert results == []

    def test_targeting_no_links_returns_empty(self, db):
        """Querying reverse links for non-existent target returns empty list."""
        with db.session() as s:
            results = db.get_similarity_links_targeting(s, "nonexistent")
        assert results == []

    def test_insert_or_replace_on_duplicate_id(self, db):
        """Storing a link with the same ID replaces the existing one."""
        with db.session() as s:
            db.store_similarity_link(s, _make_link(id="dup", similarity=0.80))
            db.store_similarity_link(s, _make_link(id="dup", similarity=0.99))
        with db.session() as s:
            results = db.get_similarity_links(s, "cache-A")
        assert len(results) == 1
        assert results[0].similarity == pytest.approx(0.99)
