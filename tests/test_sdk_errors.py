"""SDK error-path tests for BitmodClient and AsyncBitmodClient."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

pytest.importorskip("bitmod_client", reason="bitmod_client SDK not installed")

from bitmod_client.client import BitmodClient, _raise_for_status  # noqa: E402
from bitmod_client.exceptions import (  # noqa: E402
    BitmodAuthError,
    BitmodConnectionError,
    BitmodError,
    BitmodNotFoundError,
    BitmodRateLimitError,
    BitmodServerError,
    BitmodTimeoutError,
    BitmodValidationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> BitmodClient:
    return BitmodClient(base_url="http://localhost:9999", api_key="bm_test_key")


def _mock_response(status_code: int, json_body: dict | None = None, headers: dict | None = None) -> httpx.Response:
    """Build a fake httpx.Response with the given status and body."""
    resp = httpx.Response(
        status_code,
        json=json_body or {},
        headers=headers or {},
        request=httpx.Request("GET", "http://localhost:9999/test"),
    )
    return resp


# ---------------------------------------------------------------------------
# _raise_for_status unit tests
# ---------------------------------------------------------------------------


class TestRaiseForStatus:
    def test_success_does_not_raise(self):
        resp = _mock_response(200, {"ok": True})
        _raise_for_status(resp)  # should not raise

    def test_401_raises_auth_error(self):
        resp = _mock_response(401, {"detail": "Invalid API key."})
        with pytest.raises(BitmodAuthError, match="Invalid API key"):
            _raise_for_status(resp)

    def test_403_raises_auth_error(self):
        resp = _mock_response(403, {"detail": "Forbidden"})
        with pytest.raises(BitmodAuthError):
            _raise_for_status(resp)

    def test_404_raises_not_found(self):
        resp = _mock_response(404, {"detail": "Not found"})
        with pytest.raises(BitmodNotFoundError, match="Not found"):
            _raise_for_status(resp)

    def test_422_raises_validation_error(self):
        resp = _mock_response(422, {"detail": "Validation failed"})
        with pytest.raises(BitmodValidationError):
            _raise_for_status(resp)

    def test_429_raises_rate_limit_with_retry_after(self):
        resp = _mock_response(429, {"detail": "Too many requests"}, headers={"Retry-After": "30"})
        with pytest.raises(BitmodRateLimitError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.retry_after == 30.0
        assert exc_info.value.status_code == 429

    def test_429_without_retry_after_header(self):
        resp = _mock_response(429, {"detail": "Slow down"})
        with pytest.raises(BitmodRateLimitError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.retry_after is None

    def test_500_raises_server_error(self):
        resp = _mock_response(500, {"detail": "Internal server error"})
        with pytest.raises(BitmodServerError):
            _raise_for_status(resp)

    def test_502_raises_server_error(self):
        resp = _mock_response(502, {"detail": "Bad gateway"})
        with pytest.raises(BitmodServerError):
            _raise_for_status(resp)

    def test_418_raises_generic_bitmod_error(self):
        resp = _mock_response(418, {"detail": "I'm a teapot"})
        with pytest.raises(BitmodError):
            _raise_for_status(resp)


# ---------------------------------------------------------------------------
# BitmodClient._request integration tests (mocked transport)
# ---------------------------------------------------------------------------


class TestClientErrorPaths:
    def test_connection_refused(self):
        client = _make_client()
        with patch.object(client._client, "request", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(BitmodConnectionError, match="Cannot connect"):
                client.health()

    def test_timeout(self):
        client = _make_client()
        with patch.object(client._client, "request", side_effect=httpx.ReadTimeout("timed out")):
            with pytest.raises(BitmodTimeoutError, match="timed out"):
                client.health()

    def test_401_from_health(self):
        client = _make_client()
        resp = _mock_response(401, {"detail": "Invalid API key."})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(BitmodAuthError):
                client.health()

    def test_404_from_get_document(self):
        client = _make_client()
        resp = _mock_response(404, {"detail": "Document not found"})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(BitmodNotFoundError):
                client.get_document("nonexistent-id")

    def test_500_from_ask(self):
        client = _make_client()
        resp = _mock_response(500, {"detail": "Internal error"})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(BitmodServerError):
                client.ask("test query")

    def test_rate_limit_from_lookup(self):
        client = _make_client()
        resp = _mock_response(429, {"detail": "Rate limited"}, headers={"Retry-After": "60"})
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(BitmodRateLimitError) as exc_info:
                client.lookup("test query")
            assert exc_info.value.retry_after == 60.0

    def test_malformed_json_response(self):
        """Server returns 200 but body is not valid JSON — should raise JSONDecodeError."""
        client = _make_client()
        raw_resp = httpx.Response(
            200,
            content=b"this is not json",
            request=httpx.Request("GET", "http://localhost:9999/health"),
        )
        with patch.object(client._client, "request", return_value=raw_resp):
            with pytest.raises((ValueError, Exception)) as exc_info:
                client.health()
            # Must be a JSON-related error, not some other random exception
            assert "json" in type(exc_info.value).__name__.lower() or "json" in str(exc_info.value).lower()

    def test_error_body_preserved(self):
        client = _make_client()
        body = {"detail": "Unauthorized", "code": "AUTH_001"}
        resp = _mock_response(401, body)
        with patch.object(client._client, "request", return_value=resp):
            with pytest.raises(BitmodAuthError) as exc_info:
                client.health()
            assert exc_info.value.body == body
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Constructor edge cases
# ---------------------------------------------------------------------------


class TestClientConstructor:
    def test_missing_api_key_raises(self):
        import os

        env = {k: v for k, v in os.environ.items() if k != "BITMOD_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(BitmodAuthError, match="No API key"):
                BitmodClient(base_url="http://localhost:9999")

    def test_base_url_strips_trailing_slash(self):
        client = BitmodClient(base_url="http://localhost:9999/", api_key="bm_test")
        assert client._base_url == "http://localhost:9999"

    def test_base_url_from_env(self):
        import os

        with patch.dict(os.environ, {"BITMOD_BASE_URL": "http://custom:7777", "BITMOD_API_KEY": "bm_env"}):
            client = BitmodClient()
            assert client._base_url == "http://custom:7777"
