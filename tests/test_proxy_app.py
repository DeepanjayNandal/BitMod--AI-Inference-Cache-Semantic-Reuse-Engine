"""Tests for the hardened proxy app."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")


def _noop_auth_dep():
    """Return a no-op auth dependency that bypasses annotation resolution issues on reload."""
    from bitmod.auth import AuthUser

    async def _noop(request=None):
        return AuthUser(subject="anonymous", scopes=["read"], auth_method="none")

    return _noop


def _make_app(proxy_instance=None, backend_side_effect=None):
    """Create a fresh proxy app by calling the factory with mocks.

    Avoids importlib.reload which breaks FastAPI annotation resolution
    when ``from __future__ import annotations`` is used.
    """
    from fastapi.testclient import TestClient

    noop = _noop_auth_dep()

    with (
        patch("bitmod.adapters.get_backend") as mock_backend,
        patch("bitmod.adapters.get_llm") as mock_llm,
        patch("bitmod.adapters.get_embedder") as mock_embedder,
        patch("bitmod.proxy.base.BitmodProxy") as mock_proxy_cls,
        patch("bitmod.auth._AUTH_ENABLED", False),
        patch("bitmod.auth.require_auth", return_value=noop),
    ):
        if backend_side_effect:
            mock_backend.side_effect = backend_side_effect
        else:
            be = MagicMock()
            be.initialize = MagicMock()
            mock_backend.return_value = be
        mock_llm.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()

        if proxy_instance is not None:
            mock_proxy_cls.return_value = proxy_instance

        from bitmod.proxy.app import create_proxy_app

        fresh_app = create_proxy_app()

        # Reset rate-limit state (module-level dict is shared)
        import bitmod.proxy.app as proxy_module

        proxy_module._rate_buckets.clear()

        tc = TestClient(fresh_app, raise_server_exceptions=False)
        yield tc, proxy_module


@pytest.fixture()
def client():
    """Create TestClient for proxy app with fresh factory call."""
    saved = {}
    overrides = {
        "BITMOD_AUTH_ENABLED": "false",
        "BITMOD_DB_BACKEND": "sqlite",
        "BITMOD_SQLITE_PATH": ":memory:",
    }
    for k, v in overrides.items():
        saved[k] = os.environ.get(k)
        os.environ[k] = v

    proxy_instance = MagicMock()
    proxy_instance.handle_completion = AsyncMock(
        return_value={"id": "test", "choices": [{"message": {"content": "hi"}}]}
    )

    for tc, _ in _make_app(proxy_instance=proxy_instance):
        yield tc

    for k, orig in saved.items():
        if orig is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = orig


# ---- Health endpoints ----


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "bitmod-proxy"


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_has_version(client):
    resp = client.get("/health")
    assert "version" in resp.json()


# ---- Security headers ----


def test_security_header_nosniff(client):
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_security_header_frame_deny(client):
    resp = client.get("/health")
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_security_header_hsts(client):
    resp = client.get("/health")
    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_security_header_referrer_policy(client):
    resp = client.get("/health")
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_security_header_permissions_policy(client):
    resp = client.get("/health")
    assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_v1_cache_control(client):
    """API paths should have no-store cache headers."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert "no-store" in resp.headers.get("Cache-Control", "")


# ---- CSRF protection ----


def test_csrf_blocks_post_without_header(client):
    """POST to API endpoint without X-Requested-With should be 403 when auth disabled."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 403
    assert "X-Requested-With" in resp.json()["error"]


def test_csrf_allows_post_with_header(client):
    """POST with X-Requested-With header should pass CSRF and succeed."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data


def test_csrf_skips_health_on_post(client):
    """POST to /health should not be blocked by CSRF (path is exempted)."""
    resp = client.post("/health")
    assert resp.status_code == 405


# ---- Body size limit ----


def test_body_too_large_via_content_length(client):
    """Content-Length header exceeding 1MB should get 413."""
    resp = client.post(
        "/v1/chat/completions",
        content=b"x",
        headers={
            "Content-Length": str(2 * 1024 * 1024),
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert resp.status_code == 413


def test_body_within_limit(client):
    """Small body should pass size check and reach the handler successfully."""
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200


# ---- Rate limiting ----


def test_rate_limit_header_present(client):
    resp = client.get("/health")
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Limit" in resp.headers


def test_rate_limit_remaining_decrements(client):
    """Remaining count should decrease with requests."""
    r1 = client.get("/health")
    remaining1 = int(r1.headers["X-RateLimit-Remaining"])
    r2 = client.get("/health")
    remaining2 = int(r2.headers["X-RateLimit-Remaining"])
    assert remaining2 < remaining1


def test_rate_limit_429_after_threshold(client):
    """Exceeding rate limit should return 429."""
    import bitmod.proxy.app as proxy_module

    original_limit = proxy_module._RATE_LIMIT
    proxy_module._RATE_LIMIT = 3
    proxy_module._rate_buckets.clear()

    try:
        for _ in range(3):
            client.get("/health")
        resp = client.get("/health")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert resp.json()["error"] == "Rate limit exceeded. Try again later."
    finally:
        proxy_module._RATE_LIMIT = original_limit
        proxy_module._rate_buckets.clear()


# ---- Error sanitization ----


def test_500_returns_generic_message():
    """When the proxy raises, the error response should be generic, not leak internals."""
    proxy_instance = MagicMock()
    proxy_instance.handle_completion = AsyncMock(
        side_effect=RuntimeError("Connection to db password=hunter2 failed with Traceback secret=abc")
    )

    for tc, _ in _make_app(proxy_instance=proxy_instance):
        resp = tc.post(
            "/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "Internal server error."
        raw = str(body)
        assert "hunter2" not in raw
        assert "Traceback" not in raw
        assert "password" not in raw
        assert "secret" not in raw


# ---- Malformed JSON ----


def test_malformed_json_returns_400(client):
    """Malformed JSON should return 400 from our handler."""
    resp = client.post(
        "/v1/chat/completions",
        content=b"{not valid json!!!",
        headers={
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid JSON body."


# ---- Response time header ----


def test_response_time_header_present(client):
    resp = client.get("/health")
    assert "X-Response-Time" in resp.headers
    assert resp.headers["X-Response-Time"].endswith("ms")


def test_response_time_header_numeric(client):
    resp = client.get("/health")
    value = resp.headers["X-Response-Time"]
    ms_str = value.replace("ms", "")
    assert float(ms_str) >= 0


# ---- API docs disabled ----


def test_docs_disabled_without_debug(client):
    """When BITMOD_DEBUG is not set, /docs should 404."""
    resp = client.get("/docs")
    assert resp.status_code == 404


def test_redoc_disabled_without_debug(client):
    resp = client.get("/redoc")
    assert resp.status_code == 404


def test_openapi_disabled_without_debug(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 404


# ---- Models endpoint ----


def test_list_models_returns_list(client):
    """With auth disabled, /v1/models should return 200 with list structure."""
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)


# ---- Proxy not initialized ----


def test_proxy_none_returns_503():
    """When proxy fails to initialize, chat endpoint returns 503."""
    for tc, _ in _make_app(backend_side_effect=RuntimeError("no db")):
        resp = tc.post(
            "/v1/chat/completions",
            json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 503
        assert resp.json()["error"] == "Proxy not initialized."


# ---- Invalid Content-Length ----


def test_invalid_content_length(client):
    """Invalid (non-numeric) Content-Length should be rejected with 400."""
    resp = client.post(
        "/v1/chat/completions",
        content=b"{}",
        headers={
            "Content-Length": "not-a-number",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid Content-Length header."
