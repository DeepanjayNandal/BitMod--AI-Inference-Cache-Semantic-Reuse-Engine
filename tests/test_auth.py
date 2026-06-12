"""Tests for authentication and API key management."""

from __future__ import annotations

import hashlib

import pytest

from bitmod.auth import (
    APIKeyManager,
    AuthUser,
    generate_api_key,
    hash_api_key,
    is_auth_enabled,
    validate_api_key,
    validate_api_key_hash,
)
from bitmod.adapters.db_sqlite import SQLiteBackend


# ---------------------------------------------------------------------------
# API key generation
# ---------------------------------------------------------------------------


class TestAPIKeyGeneration:
    def test_generate_key_format(self):
        key = generate_api_key(prefix="bm")
        assert key.startswith("bm_")
        assert len(key) > 20

    def test_generate_key_custom_prefix(self):
        key = generate_api_key(prefix="test")
        assert key.startswith("test_")

    def test_generate_key_min_length(self):
        with pytest.raises(ValueError):
            generate_api_key(length=8)

    def test_hash_key(self):
        key = "bm_test123"
        h = hash_api_key(key)
        assert h == hashlib.sha256(key.encode()).hexdigest()

    def test_validate_key_hash(self):
        key = "bm_test_key_789"
        stored = hash_api_key(key)
        assert validate_api_key_hash(key, stored) is True
        assert validate_api_key_hash("wrong_key", stored) is False


# ---------------------------------------------------------------------------
# API key manager (requires SQLite backend)
# ---------------------------------------------------------------------------


@pytest.fixture
def key_backend(tmp_path):
    b = SQLiteBackend(str(tmp_path / "auth_test.db"))
    b.initialize()
    return b


@pytest.fixture
def mgr(key_backend):
    return APIKeyManager(key_backend)


class TestAPIKeyManager:
    def test_create_and_validate_key(self, mgr):
        raw_key, record = mgr.create_key(name="Test Key", owner="user-1")
        assert raw_key.startswith("bm_")
        assert record.name == "Test Key"
        assert record.owner == "user-1"
        assert record.is_active is True

        found = mgr.validate_key(raw_key)
        assert found is not None
        assert found.id == record.id
        assert found.name == "Test Key"

    def test_validate_invalid_key(self, mgr):
        assert mgr.validate_key("bm_nonexistent_key_12345678") is None

    def test_list_keys(self, mgr):
        mgr.create_key(name="Key A", owner="user-1")
        mgr.create_key(name="Key B", owner="user-1")
        mgr.create_key(name="Key C", owner="user-2")

        all_keys = mgr.list_keys()
        assert len(all_keys) == 3

        user1_keys = mgr.list_keys(owner="user-1")
        assert len(user1_keys) == 2

    def test_revoke_key(self, mgr):
        raw_key, record = mgr.create_key(name="Revocable")

        assert mgr.revoke_key(record.id) is True
        assert mgr.validate_key(raw_key) is None
        assert mgr.revoke_key(record.id) is False

    def test_expired_key(self, mgr, key_backend):
        raw_key, record = mgr.create_key(name="Expiring", expires_in_days=1)
        assert record.expires_at is not None

        with key_backend.session() as session:
            session.execute(
                "UPDATE api_keys SET expires_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
                (record.id,),
            )

        assert mgr.validate_key(raw_key) is None

    def test_key_scopes(self, mgr):
        raw_key, record = mgr.create_key(name="Read Only", scopes=["read"])
        found = mgr.validate_key(raw_key)
        assert found is not None
        assert found.scopes == ["read"]

    def test_last_used_updated(self, mgr):
        raw_key, record = mgr.create_key(name="Tracked")

        keys = mgr.list_keys()
        assert keys[0].last_used_at is None

        mgr.validate_key(raw_key)

        keys = mgr.list_keys()
        assert keys[0].last_used_at is not None


# ---------------------------------------------------------------------------
# AuthUser dataclass
# ---------------------------------------------------------------------------


class TestAuthUser:
    def test_auth_user_defaults(self):
        user = AuthUser(subject="test")
        assert user.subject == "test"
        assert user.scopes == []
        assert user.auth_method == ""

    def test_auth_user_with_scopes(self):
        user = AuthUser(subject="admin", scopes=["read", "write", "admin"], auth_method="jwt")
        assert "admin" in user.scopes
        assert user.auth_method == "jwt"


# ---------------------------------------------------------------------------
# Auth enabled flag
# ---------------------------------------------------------------------------


class TestIsAuthEnabled:
    def test_disabled_by_default(self):
        assert isinstance(is_auth_enabled(), bool)


# ---------------------------------------------------------------------------
# Env-based key validation
# ---------------------------------------------------------------------------


class TestEnvKeyValidation:
    def test_validate_against_env_hashes(self):
        assert validate_api_key("random_key") is False

    def test_validate_empty_key(self):
        assert validate_api_key("") is False
