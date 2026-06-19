"""Tests for JWT HS256 token creation, verification, and revocation."""

from __future__ import annotations

import time
import uuid

import pytest

jwt_lib = pytest.importorskip("jwt", reason="PyJWT required")


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch):
    """Configure HS256 JWT environment for every test in this module."""
    secret = "a" * 64  # 64 chars, well above the 32-char minimum
    monkeypatch.setenv("BITMOD_JWT_SECRET", secret)
    monkeypatch.setenv("BITMOD_AUTH_ENABLED", "true")
    monkeypatch.setenv("BITMOD_JWT_ALGORITHM", "HS256")

    import bitmod.auth as auth_mod

    monkeypatch.setattr(auth_mod, "_JWT_SECRET", secret)
    monkeypatch.setattr(auth_mod, "_JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(auth_mod, "_AUTH_ENABLED", True)

    # Clear revocation store between tests
    with auth_mod._revoked_lock:
        auth_mod._revoked_tokens.clear()

    yield


# ---------------------------------------------------------------------------
# Token creation and claim structure
# ---------------------------------------------------------------------------


class TestJWTCreation:
    def test_create_and_verify_roundtrip(self):
        from bitmod.auth import create_jwt_token, verify_jwt_token

        token = create_jwt_token(subject="user-1", scopes=["read", "write"])
        user = verify_jwt_token(token)
        assert user is not None
        assert user.subject == "user-1"
        assert user.auth_method == "jwt"

    def test_token_contains_required_claims(self):
        from bitmod.auth import _JWT_SECRET, create_jwt_token

        token = create_jwt_token(subject="svc-abc", scopes=["admin"])
        payload = jwt_lib.decode(token, _JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "svc-abc"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload
        assert payload["scopes"] == ["admin"]

    def test_jti_is_valid_uuid(self):
        from bitmod.auth import _JWT_SECRET, create_jwt_token

        token = create_jwt_token(subject="u")
        payload = jwt_lib.decode(token, _JWT_SECRET, algorithms=["HS256"])
        parsed = uuid.UUID(payload["jti"])
        assert parsed.version == 4

    def test_scopes_preserved(self):
        from bitmod.auth import create_jwt_token, verify_jwt_token

        scopes = ["read", "write", "admin"]
        token = create_jwt_token(subject="x", scopes=scopes)
        user = verify_jwt_token(token)
        assert user is not None
        assert user.scopes == scopes

    def test_extra_claims_included(self):
        from bitmod.auth import _JWT_SECRET, create_jwt_token

        token = create_jwt_token(
            subject="u",
            extra_claims={"org": "acme", "role": "manager"},
        )
        payload = jwt_lib.decode(token, _JWT_SECRET, algorithms=["HS256"])
        assert payload["org"] == "acme"
        assert payload["role"] == "manager"

    def test_extra_claims_cannot_override_core(self):
        from bitmod.auth import _JWT_SECRET, create_jwt_token

        token = create_jwt_token(
            subject="real-user",
            extra_claims={"sub": "hijacked", "jti": "bad-id"},
        )
        payload = jwt_lib.decode(token, _JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == "real-user"
        assert payload["jti"] != "bad-id"

    def test_default_scopes_empty_list(self):
        from bitmod.auth import create_jwt_token, verify_jwt_token

        token = create_jwt_token(subject="u")
        user = verify_jwt_token(token)
        assert user is not None
        assert user.scopes == []


# ---------------------------------------------------------------------------
# Token verification failures
# ---------------------------------------------------------------------------


class TestJWTVerification:
    def test_expired_token_returns_none(self):
        from bitmod.auth import create_jwt_token, verify_jwt_token

        token = create_jwt_token(subject="u", expiry_seconds=-1)
        assert verify_jwt_token(token) is None

    def test_invalid_token_returns_none(self):
        from bitmod.auth import verify_jwt_token

        assert verify_jwt_token("not.a.jwt") is None
        assert verify_jwt_token("") is None

    def test_wrong_secret_returns_none(self, monkeypatch):
        from bitmod.auth import _JWT_SECRET, create_jwt_token, verify_jwt_token

        token = create_jwt_token(subject="u")

        import bitmod.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_JWT_SECRET", "b" * 64)
        assert verify_jwt_token(token) is None

        # Restore so teardown works
        monkeypatch.setattr(auth_mod, "_JWT_SECRET", _JWT_SECRET)

    def test_tampered_payload_returns_none(self):
        from bitmod.auth import create_jwt_token, verify_jwt_token

        token = create_jwt_token(subject="u")
        parts = token.split(".")
        # Flip a character in the payload
        tampered = parts[0] + "." + parts[1][::-1] + "." + parts[2]
        assert verify_jwt_token(tampered) is None


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


class TestJWTRevocation:
    def test_revoked_token_returns_none(self):
        from bitmod.auth import _JWT_SECRET, create_jwt_token, revoke_token, verify_jwt_token

        token = create_jwt_token(subject="u")
        payload = jwt_lib.decode(token, _JWT_SECRET, algorithms=["HS256"])
        jti = payload["jti"]

        revoke_token(jti)
        assert verify_jwt_token(token) is None

    def test_revoke_empty_jti_is_noop(self):
        from bitmod.auth import revoke_token

        revoke_token("")  # should not raise

    def test_revocation_store_bounded(self, monkeypatch):
        import bitmod.auth as auth_mod

        monkeypatch.setattr(auth_mod, "_MAX_REVOKED_TOKENS", 5)

        from bitmod.auth import _revoked_tokens, revoke_token

        for i in range(10):
            revoke_token(f"jti-{i}")

        assert len(_revoked_tokens) <= 5

    def test_duplicate_revoke_refreshes_entry(self):
        from bitmod.auth import _revoked_tokens, revoke_token

        revoke_token("jti-dup", expires_at=time.time() + 100)
        revoke_token("jti-dup", expires_at=time.time() + 200)
        # Should still be only one entry
        assert list(_revoked_tokens.keys()).count("jti-dup") == 1

    def test_cleanup_removes_expired_revocations(self, monkeypatch):
        from bitmod.auth import _cleanup_expired_revocations, _revoked_tokens, revoke_token

        past = time.time() - 10
        revoke_token("old-jti", expires_at=past)
        revoke_token("new-jti", expires_at=time.time() + 3600)

        _cleanup_expired_revocations()

        assert "old-jti" not in _revoked_tokens
        assert "new-jti" in _revoked_tokens
