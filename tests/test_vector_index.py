"""Tests for NumpyVectorIndex (in-memory cosine similarity search)."""

from __future__ import annotations

import math

import pytest
from bitmod.vector_index import VectorIndex


@pytest.fixture
def index():
    """Empty vector index."""
    return VectorIndex(max_size=100)


def _unit_vec(dim: int, active: int) -> list[float]:
    """Create a one-hot vector: 1.0 at position `active`, 0 elsewhere."""
    v = [0.0] * dim
    v[active] = 1.0
    return v


class TestVectorIndexAdd:
    """Tests for adding vectors to the index."""

    def test_add_increments_count(self, index):
        """Adding a vector increases the count."""
        assert index.count() == 0
        index.add("v1", [1.0, 0.0, 0.0])
        assert index.count() == 1
        index.add("v2", [0.0, 1.0, 0.0])
        assert index.count() == 2

    def test_add_duplicate_id_replaces(self, index):
        """Adding with same ID replaces the previous vector."""
        index.add("v1", [1.0, 0.0, 0.0])
        index.add("v1", [0.0, 1.0, 0.0])
        assert index.count() == 1
        # Search with the new direction should match
        results = index.search([0.0, 1.0, 0.0], k=1)
        assert results[0][0] == "v1"
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)

    def test_vectors_are_l2_normalized(self, index):
        """Vectors are normalized on add, so unnormalized input still works."""
        index.add("v1", [3.0, 4.0])  # norm = 5
        # Searching with same direction (normalized) should give similarity ~1.0
        results = index.search([3.0, 4.0], k=1)
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)

    def test_max_size_eviction(self):
        """Index evicts oldest entry when max_size is exceeded."""
        idx = VectorIndex(max_size=3)
        idx.add("v1", [1.0, 0.0])
        idx.add("v2", [0.0, 1.0])
        idx.add("v3", [1.0, 1.0])
        assert idx.count() == 3
        idx.add("v4", [0.5, 0.5])
        assert idx.count() == 3
        # v1 should be gone
        results = idx.search([1.0, 0.0], k=10)
        ids = [r[0] for r in results]
        assert "v1" not in ids


class TestVectorIndexSearch:
    """Tests for searching vectors."""

    def test_search_returns_sorted_by_similarity(self, index):
        """Results are sorted by descending cosine similarity."""
        index.add("exact", [1.0, 0.0, 0.0])
        index.add("partial", [0.7, 0.7, 0.0])
        index.add("orthogonal", [0.0, 0.0, 1.0])

        results = index.search([1.0, 0.0, 0.0], k=3)
        assert len(results) == 3
        assert results[0][0] == "exact"
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)
        # Similarities should be descending
        sims = [r[1] for r in results]
        assert sims == sorted(sims, reverse=True)

    def test_search_top_k(self, index):
        """k parameter limits number of results."""
        for i in range(10):
            index.add(f"v{i}", _unit_vec(10, i))
        results = index.search(_unit_vec(10, 0), k=3)
        assert len(results) == 3

    def test_search_k_larger_than_index(self, index):
        """When k > number of vectors, returns all vectors."""
        index.add("v1", [1.0, 0.0])
        index.add("v2", [0.0, 1.0])
        results = index.search([1.0, 0.0], k=100)
        assert len(results) == 2

    def test_search_empty_index(self, index):
        """Searching an empty index returns empty list."""
        results = index.search([1.0, 0.0, 0.0], k=5)
        assert results == []

    def test_search_zero_vector_returns_empty(self, index):
        """Searching with a zero vector returns empty (can't normalize)."""
        index.add("v1", [1.0, 0.0])
        results = index.search([0.0, 0.0], k=5)
        assert results == []

    def test_search_finds_most_similar(self, index):
        """Search correctly identifies the most similar vector."""
        index.add("north", [0.0, 1.0])
        index.add("east", [1.0, 0.0])
        index.add("northeast", [1.0, 1.0])

        results = index.search([0.1, 0.9], k=1)
        assert results[0][0] == "north"


class TestVectorIndexRemove:
    """Tests for removing vectors."""

    def test_remove_decrements_count(self, index):
        """Removing a vector decreases the count."""
        index.add("v1", [1.0, 0.0])
        index.add("v2", [0.0, 1.0])
        index.remove("v1")
        assert index.count() == 1

    def test_remove_nonexistent_is_noop(self, index):
        """Removing a non-existent ID does nothing."""
        index.add("v1", [1.0, 0.0])
        index.remove("nonexistent")
        assert index.count() == 1

    def test_removed_vector_not_in_search(self, index):
        """Removed vector no longer appears in search results."""
        index.add("v1", [1.0, 0.0])
        index.add("v2", [0.0, 1.0])
        index.remove("v1")
        results = index.search([1.0, 0.0], k=10)
        ids = [r[0] for r in results]
        assert "v1" not in ids

    def test_remove_all_then_search(self, index):
        """Removing all vectors and then searching returns empty."""
        index.add("v1", [1.0, 0.0])
        index.remove("v1")
        assert index.count() == 0
        results = index.search([1.0, 0.0], k=5)
        assert results == []

    def test_remove_and_readd(self, index):
        """Can remove a vector and re-add it with a different embedding."""
        index.add("v1", [1.0, 0.0])
        index.remove("v1")
        index.add("v1", [0.0, 1.0])
        results = index.search([0.0, 1.0], k=1)
        assert results[0][0] == "v1"
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)


class TestVectorIndexCount:
    """Tests for count()."""

    def test_empty_count(self, index):
        assert index.count() == 0

    def test_count_after_adds_and_removes(self, index):
        index.add("a", [1.0, 0.0])
        index.add("b", [0.0, 1.0])
        index.add("c", [1.0, 1.0])
        assert index.count() == 3
        index.remove("b")
        assert index.count() == 2


class TestVectorIndexDecodeEmbedding:
    """Tests for the static _decode_embedding helper."""

    def test_decode_list(self):
        result = VectorIndex._decode_embedding([1.0, 2.0, 3.0])
        assert result == [1.0, 2.0, 3.0]

    def test_decode_bytes(self):
        import struct

        data = struct.pack("3f", 1.0, 2.0, 3.0)
        result = VectorIndex._decode_embedding(data)
        assert len(result) == 3
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(2.0)

    def test_decode_none_input(self):
        assert VectorIndex._decode_embedding(None) is None

    def test_decode_string_returns_none(self):
        assert VectorIndex._decode_embedding("not bytes") is None


class TestVectorIndexPythonFallback:
    """Tests that the pure-Python fallback path works when numpy is unavailable."""

    def test_fallback_search(self):
        """Force the Python fallback path and verify search works."""
        idx = VectorIndex(max_size=100)
        # Populate _rows directly (bypassing numpy path) to test _search_python
        for id_, vec in [("north", [0.0, 1.0]), ("east", [1.0, 0.0]), ("ne", [1.0, 1.0])]:
            norm = math.sqrt(sum(x * x for x in vec))
            idx._rows.append([x / norm for x in vec])
            idx._ids.append(id_)
            idx._id_to_pos[id_] = len(idx._ids) - 1

        # Use the python path explicitly
        results = idx._search_python([0.0, 1.0], k=2)
        assert len(results) == 2
        assert results[0][0] == "north"
        assert results[0][1] == pytest.approx(1.0, abs=1e-5)

    def test_fallback_zero_query(self):
        """Python fallback with zero vector returns empty."""
        idx = VectorIndex()
        idx._rows = [[1.0, 0.0]]
        idx._ids = ["v1"]
        idx._id_to_pos = {"v1": 0}
        results = idx._search_python([0.0, 0.0], k=5)
        assert results == []
