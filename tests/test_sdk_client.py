"""Tests for the BitMod Python SDK client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

pytest.importorskip("bitmod_client", reason="bitmod-client SDK not installed")
from bitmod_client.client import BitmodClient, _default_headers  # noqa: E402
from bitmod_client.exceptions import (  # noqa: E402
    BitmodAuthError,
    BitmodConnectionError,
    BitmodNotFoundError,
    BitmodRateLimitError,
    BitmodServerError,
    BitmodTimeoutError,
    BitmodValidationError,
)

# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestClientConstructor:

    def test_sets_base_url(self):
        client = BitmodClient(base_url="http://myhost:9000", api_key="bm_test")
        assert client._base_url == "http://myhost:9000"
        client.close()

    def test_strips_trailing_slash(self):
        client = BitmodClient(base_url="http://myhost:9000/", api_key="bm_test")
        assert client._base_url == "http://myhost:9000"
        client.close()

    def test_sets_api_key(self):
        client = BitmodClient(base_url="http://localhost", api_key="bm_secret")
        assert client._api_key == "bm_secret"
        client.close()

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("BITMOD_API_KEY", raising=False)
        with pytest.raises(BitmodAuthError, match="No API key"):
            BitmodClient(base_url="http://localhost")

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("BITMOD_API_KEY", "bm_from_env")
        client = BitmodClient(base_url="http://localhost")
        assert client._api_key == "bm_from_env"
        client.close()

    def test_default_base_url(self, monkeypatch):
        monkeypatch.delenv("BITMOD_BASE_URL", raising=False)
        client = BitmodClient(api_key="bm_test")
        assert client._base_url == "http://localhost:8000"
        client.close()


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestHeaders:

    def test_includes_authorization(self):
        headers = _default_headers("bm_test123")
        assert headers["Authorization"] == "Bearer bm_test123"

    def test_includes_user_agent(self):
        headers = _default_headers("bm_test")
        assert "bitmod-python" in headers["User-Agent"]

    def test_includes_accept_json(self):
        headers = _default_headers("bm_test")
        assert headers["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# API Methods -- request payloads
# ---------------------------------------------------------------------------


class TestAsk:

    @pytest.fixture
    def client(self):
        c = BitmodClient(base_url="http://test:8000", api_key="bm_test")
        yield c
        c.close()

    def test_sends_correct_json_body(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.is_success = True
        mock_resp.json.return_value = {"answer": "42", "cached": True}

        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.ask("What is 6*7?", model="gpt-4o", llm_key="sk-abc", temperature=0.5, system_prompt="Be concise")

        call_args = mock_req.call_args
        assert call_args[0] == ("POST", "/v1/ask")
        payload = call_args[1]["json"]
        assert payload["query"] == "What is 6*7?"
        assert payload["model"] == "gpt-4o"
        assert payload["llm_key"] == "sk-abc"
        assert payload["temperature"] == 0.5
        assert payload["system_prompt"] == "Be concise"

    def test_omits_optional_fields(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.is_success = True
        mock_resp.json.return_value = {"answer": "ok", "cached": False}

        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.ask("Hello")

        payload = mock_req.call_args[1]["json"]
        assert "model" not in payload
        assert "llm_key" not in payload
        assert "system_prompt" not in payload
        assert payload["temperature"] == 0.0


class TestSearch:

    @pytest.fixture
    def client(self):
        c = BitmodClient(base_url="http://test:8000", api_key="bm_test")
        yield c
        c.close()

    def test_sends_correct_params(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.is_success = True
        mock_resp.json.return_value = {"results": []}

        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.search("HIPAA regulations", limit=5)

        payload = mock_req.call_args[1]["json"]
        assert payload["query"] == "HIPAA regulations"
        assert payload["limit"] == 5


class TestIngestText:

    @pytest.fixture
    def client(self):
        c = BitmodClient(base_url="http://test:8000", api_key="bm_test")
        yield c
        c.close()

    def test_sends_correct_body(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.is_success = True
        mock_resp.json.return_value = {"id": "doc-1", "chunks": 3}

        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.ingest_text("Some legal text", title="Doc Title", tags=["law", "test"])

        call_args = mock_req.call_args
        assert call_args[0] == ("POST", "/v1/ingest/text")
        payload = call_args[1]["json"]
        assert payload["text"] == "Some legal text"
        assert payload["title"] == "Doc Title"
        assert payload["tags"] == ["law", "test"]


class TestUsage:

    @pytest.fixture
    def client(self):
        c = BitmodClient(base_url="http://test:8000", api_key="bm_test")
        yield c
        c.close()

    def test_calls_correct_endpoint(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.is_success = True
        mock_resp.json.return_value = {"total_queries": 100, "cache_hits": 80}

        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            client.usage(days=7)

        call_args = mock_req.call_args
        assert call_args[0] == ("GET", "/v1/usage")
        params = call_args[1]["params"]
        assert params["days"] == 7
        assert "limit" in params
        assert "offset" in params


class TestHealth:

    @pytest.fixture
    def client(self):
        c = BitmodClient(base_url="http://test:8000", api_key="bm_test")
        yield c
        c.close()

    def test_calls_health_endpoint(self, client):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.is_success = True
        mock_resp.json.return_value = {"status": "ok", "version": "0.2.0"}

        with patch.object(client._client, "request", return_value=mock_resp) as mock_req:
            result = client.health()

        call_args = mock_req.call_args
        assert call_args[0] == ("GET", "/health")
        assert result.status == "ok"
        assert result.healthy is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:

    @pytest.fixture
    def client(self):
        c = BitmodClient(base_url="http://test:8000", api_key="bm_test")
        yield c
        c.close()

    def _mock_error_response(self, status_code, detail="error", headers=None):
        resp = MagicMock(spec=httpx.Response)
        resp.is_success = False
        resp.status_code = status_code
        resp.json.return_value = {"detail": detail}
        resp.text = detail
        resp.headers = headers or {}
        return resp

    def test_401_raises_auth_error(self, client):
        mock_resp = self._mock_error_response(401, "Unauthorized")
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BitmodAuthError):
                client.health()

    def test_403_raises_auth_error(self, client):
        mock_resp = self._mock_error_response(403, "Forbidden")
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BitmodAuthError):
                client.health()

    def test_404_raises_not_found(self, client):
        mock_resp = self._mock_error_response(404, "Not found")
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BitmodNotFoundError):
                client.health()

    def test_422_raises_validation_error(self, client):
        mock_resp = self._mock_error_response(422, "Invalid input")
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BitmodValidationError):
                client.ask("bad query")

    def test_429_raises_rate_limit_error(self, client):
        mock_resp = self._mock_error_response(429, "Too many requests", headers={"Retry-After": "30"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BitmodRateLimitError) as exc_info:
                client.ask("query")
            assert exc_info.value.retry_after == 30.0

    def test_500_raises_server_error(self, client):
        mock_resp = self._mock_error_response(500, "Internal error")
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BitmodServerError):
                client.health()

    def test_connection_error(self, client):
        with patch.object(client._client, "request", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(BitmodConnectionError, match="Cannot connect"):
                client.health()

    def test_timeout_error(self, client):
        with patch.object(client._client, "request", side_effect=httpx.ReadTimeout("timed out")):
            with pytest.raises(BitmodTimeoutError):
                client.health()


class TestContextManager:

    def test_context_manager_closes(self):
        with BitmodClient(base_url="http://test:8000", api_key="bm_test") as client:
            assert client._client is not None
        # After exit, close() has been called (no crash = success)
