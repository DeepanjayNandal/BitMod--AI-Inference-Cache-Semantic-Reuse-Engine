"""Tests for namespace isolation — multi-tenant cache scoping."""

from __future__ import annotations

import pytest

from bitmod.adapters.db_sqlite import SQLiteBackend
from bitmod.cache_engine import compute_answer_key, store_answer, try_cache
from bitmod.namespaces import NamespaceManager


@pytest.fixture
def ns_backend(tmp_path):
    """Fresh SQLiteBackend for namespace tests."""
    b = SQLiteBackend(path=str(tmp_path / "ns_test.db"))
    b.initialize()
    return b


@pytest.fixture
def mgr(ns_backend):
    return NamespaceManager(ns_backend)


OWNER = "key-owner-1"
OTHER = "key-other-2"


# ---------------------------------------------------------------------------
# CRUD basics
# ---------------------------------------------------------------------------


class TestNamespaceCRUD:
    def test_create_namespace(self, mgr):
        ns = mgr.create(name="tenant-a", owner_key_id=OWNER)
        assert ns.name == "tenant-a"
        assert ns.owner_key_id == OWNER
        assert ns.id  # UUID assigned

    def test_get_by_id(self, mgr):
        ns = mgr.create(name="by-id", owner_key_id=OWNER)
        fetched = mgr.get(ns.id)
        assert fetched is not None
        assert fetched.name == "by-id"

    def test_get_by_name(self, mgr):
        mgr.create(name="by-name", owner_key_id=OWNER)
        fetched = mgr.get_by_name("by-name")
        assert fetched is not None
        assert fetched.owner_key_id == OWNER

    def test_get_nonexistent_returns_none(self, mgr):
        assert mgr.get("no-such-id") is None
        assert mgr.get_by_name("no-such-name") is None

    def test_list_all(self, mgr):
        mgr.create(name="ns-1", owner_key_id=OWNER)
        mgr.create(name="ns-2", owner_key_id=OTHER)
        all_ns = mgr.list_all()
        assert len(all_ns) == 2

    def test_list_for_owner(self, mgr):
        mgr.create(name="ns-mine", owner_key_id=OWNER)
        mgr.create(name="ns-theirs", owner_key_id=OTHER)
        mine = mgr.list_for_owner(OWNER)
        assert len(mine) == 1
        assert mine[0].name == "ns-mine"

    def test_delete_namespace(self, mgr):
        ns = mgr.create(name="doomed", owner_key_id=OWNER)
        result = mgr.delete(ns.id, OWNER)
        assert result is True
        assert mgr.get(ns.id) is None

    def test_delete_wrong_owner_denied(self, mgr):
        ns = mgr.create(name="protected", owner_key_id=OWNER)
        result = mgr.delete(ns.id, OTHER)
        assert result is False
        assert mgr.get(ns.id) is not None

    def test_delete_nonexistent(self, mgr):
        assert mgr.delete("missing-id", OWNER) is False


# ---------------------------------------------------------------------------
# Defaults and validation
# ---------------------------------------------------------------------------


class TestNamespaceDefaults:
    def test_public_fallback_defaults_false(self, mgr):
        ns = mgr.create(name="strict-ns", owner_key_id=OWNER)
        assert ns.public_fallback is False

    def test_public_fallback_explicit_true(self, mgr):
        ns = mgr.create(name="open-ns", owner_key_id=OWNER, public_fallback=True)
        assert ns.public_fallback is True

    def test_empty_name_raises(self, mgr):
        with pytest.raises(ValueError):
            mgr.create(name="", owner_key_id=OWNER)

    def test_whitespace_name_raises(self, mgr):
        with pytest.raises(ValueError):
            mgr.create(name="   ", owner_key_id=OWNER)

    def test_invalid_isolation_raises(self, mgr):
        with pytest.raises(ValueError, match="Invalid isolation"):
            mgr.create(name="bad-iso", owner_key_id=OWNER, isolation="chaos")

    def test_empty_owner_raises(self, mgr):
        with pytest.raises(ValueError):
            mgr.create(name="no-owner", owner_key_id="")


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


class TestNamespaceAccess:
    def test_owner_has_access(self, mgr):
        ns = mgr.create(name="owned", owner_key_id=OWNER)
        assert mgr.is_accessible(ns.id, OWNER) is True

    def test_non_owner_denied_when_strict(self, mgr):
        ns = mgr.create(name="strict", owner_key_id=OWNER, public_fallback=False)
        assert mgr.is_accessible(ns.id, OTHER) is False

    def test_non_owner_allowed_when_public_fallback(self, mgr):
        ns = mgr.create(name="public", owner_key_id=OWNER, public_fallback=True)
        assert mgr.is_accessible(ns.id, OTHER) is True

    def test_nonexistent_namespace_not_accessible(self, mgr):
        assert mgr.is_accessible("fake-id", OWNER) is False


# ---------------------------------------------------------------------------
# Authenticated key ID enforcement
# ---------------------------------------------------------------------------


class TestAuthenticatedKeyId:
    def test_matching_key_id_allowed(self, mgr):
        ns = mgr.create(
            name="match",
            owner_key_id=OWNER,
            authenticated_key_id=OWNER,
        )
        assert ns.owner_key_id == OWNER

    def test_mismatched_key_id_raises_permission_error(self, mgr):
        with pytest.raises(PermissionError):
            mgr.create(
                name="mismatch",
                owner_key_id=OWNER,
                authenticated_key_id=OTHER,
            )

    def test_none_authenticated_key_id_skips_check(self, mgr):
        ns = mgr.create(
            name="no-auth-check",
            owner_key_id=OWNER,
            authenticated_key_id=None,
        )
        assert ns.owner_key_id == OWNER


# ---------------------------------------------------------------------------
# Cache isolation via namespace-scoped keys
# ---------------------------------------------------------------------------


class TestNamespaceCacheIsolation:
    def test_same_query_different_namespace_different_key(self):
        key_a = compute_answer_key("what is python", namespace_id="ns-a")
        key_b = compute_answer_key("what is python", namespace_id="ns-b")
        assert key_a != key_b

    def test_same_query_no_namespace_different_from_namespaced(self):
        key_global = compute_answer_key("what is python")
        key_ns = compute_answer_key("what is python", namespace_id="ns-1")
        assert key_global != key_ns

    def test_store_in_ns_a_lookup_in_ns_b_misses(self, ns_backend):
        with ns_backend.session() as session:
            store_answer(
                backend=ns_backend,
                session=session,
                answer_key=compute_answer_key("test query", namespace_id="ns-a"),
                question_raw="test query",
                question_normalized="test query",
                filters={},
                answer_text="answer for ns-a",
                source_sections=[],
                model_used="test",
                generation_ms=100,
                namespace_id="ns-a",
            )

        with ns_backend.session() as session:
            hit = try_cache(ns_backend, session, "test query", namespace_id="ns-b")
            assert hit is None

    def test_store_and_retrieve_same_namespace(self, ns_backend):
        with ns_backend.session() as session:
            store_answer(
                backend=ns_backend,
                session=session,
                answer_key=compute_answer_key("hello", namespace_id="ns-x"),
                question_raw="hello",
                question_normalized="hello",
                filters={},
                answer_text="hello response",
                source_sections=[],
                model_used="test",
                generation_ms=50,
                namespace_id="ns-x",
            )

        with ns_backend.session() as session:
            hit = try_cache(ns_backend, session, "hello", namespace_id="ns-x")
            assert hit is not None
            assert hit.answer_text == "hello response"
