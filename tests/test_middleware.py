"""Tests for correlation ID middleware."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from bitmod.middleware import correlation_id_middleware


class _FakeHeaders(dict):
    """Dict subclass that does case-insensitive .get() for header lookup."""

    def get(self, key, default=None):
        return super().get(key.lower(), default)


def _make_request(headers: dict | None = None):
    """Build a fake Request with the given headers."""
    raw = headers or {}
    req = MagicMock()
    req.headers = _FakeHeaders({k.lower(): v for k, v in raw.items()})
    req.method = "GET"
    req.url = MagicMock()
    req.url.path = "/v1/chat"
    return req


def _make_response(status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    return resp


class TestCorrelationIdMiddleware:
    """Verify correlation ID extraction, generation, and propagation."""

    @pytest.mark.asyncio
    async def test_generates_uuid_when_no_header(self):
        """Missing X-Correlation-ID header causes a new ID to be generated."""
        req = _make_request()
        resp = _make_response()

        async def call_next(_):
            return resp

        result = await correlation_id_middleware(req, call_next)
        cid = result.headers["X-Correlation-ID"]
        assert len(cid) == 8, "Generated correlation ID should be 8-char UUID prefix"

    @pytest.mark.asyncio
    async def test_extracts_correlation_id_from_header(self):
        """Provided X-Correlation-ID header is used as-is."""
        req = _make_request({"x-correlation-id": "my-trace-42"})
        resp = _make_response()

        async def call_next(_):
            return resp

        result = await correlation_id_middleware(req, call_next)
        assert result.headers["X-Correlation-ID"] == "my-trace-42"

    @pytest.mark.asyncio
    async def test_sets_correlation_id_in_context(self):
        """Correlation ID is stored via set_correlation_id for downstream access."""
        req = _make_request({"x-correlation-id": "ctx-test-99"})
        resp = _make_response()
        captured_cid = None

        with patch("bitmod.middleware.set_correlation_id") as mock_set:
            async def call_next(_):
                return resp

            await correlation_id_middleware(req, call_next)
            mock_set.assert_called_once_with("ctx-test-99")

    @pytest.mark.asyncio
    async def test_tenant_id_default(self):
        """Missing X-Tenant-ID defaults to 'default'."""
        req = _make_request()
        resp = _make_response()

        with patch("bitmod.middleware.set_tenant_id") as mock_set:
            async def call_next(_):
                return resp

            await correlation_id_middleware(req, call_next)
            mock_set.assert_called_once_with("default")

    @pytest.mark.asyncio
    async def test_tenant_id_extracted(self):
        """X-Tenant-ID header is forwarded to set_tenant_id."""
        req = _make_request({"x-tenant-id": "acme-corp"})
        resp = _make_response()

        with patch("bitmod.middleware.set_tenant_id") as mock_set:
            async def call_next(_):
                return resp

            await correlation_id_middleware(req, call_next)
            mock_set.assert_called_once_with("acme-corp")

    @pytest.mark.asyncio
    async def test_response_carries_correlation_header(self):
        """Response always contains X-Correlation-ID header."""
        req = _make_request()
        resp = _make_response(status_code=404)

        async def call_next(_):
            return resp

        result = await correlation_id_middleware(req, call_next)
        assert "X-Correlation-ID" in result.headers
