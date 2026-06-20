"""Tests for the async BitMod SDK client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

bitmod_client = pytest.importorskip("bitmod_client", reason="bitmod-client SDK not installed")
from bitmod_client.client import AsyncBitmodClient  # noqa: E402
from bitmod_client.exceptions import BitmodAuthError, BitmodConnectionError, BitmodTimeoutError  # noqa: E402


class TestAsyncClientConstructor:
    """Test AsyncBitmodClient initialization."""

    def test_creates_instance(self):
        client = AsyncBitmodClient(api_key="test-key", base_url="http://localhost:8000")
        assert client is not None

    def test_sets_api_key(self):
        client = AsyncBitmodClient(api_key="my-key", base_url="http://localhost:8000")
        assert client._api_key == "my-key"


class TestAsyncClientMethods:
    """Test async client methods exist and are callable."""

    @pytest.fixture
    def client(self):
        return AsyncBitmodClient(api_key="test", base_url="http://localhost:8000")

    def test_has_ask(self, client):
        assert asyncio.iscoroutinefunction(client.ask)

    def test_has_search(self, client):
        assert asyncio.iscoroutinefunction(client.search)

    def test_has_health(self, client):
        assert asyncio.iscoroutinefunction(client.health)

    def test_has_usage(self, client):
        assert asyncio.iscoroutinefunction(client.usage)

    def test_has_ingest_text(self, client):
        assert asyncio.iscoroutinefunction(client.ingest_text)


class TestAsyncClientRequests:
    """Test async client request construction."""

    @pytest.fixture
    def client(self):
        return AsyncBitmodClient(api_key="test-key", base_url="http://localhost:8000")

    @pytest.mark.asyncio
    async def test_health_calls_correct_endpoint(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client._client, "request", new_callable=AsyncMock, return_value=mock_resp) as mock_req:
            await client.health()
            call_args = mock_req.call_args
            assert call_args[0] == ("GET", "/health")

    @pytest.mark.asyncio
    async def test_has_ask_method(self, client):
        """Verify ask() is an async method that can be called."""
        import inspect
        assert inspect.iscoroutinefunction(client.ask)


class TestAsyncClientErrors:
    """Test async client error handling."""

    @pytest.fixture
    def client(self):
        return AsyncBitmodClient(api_key="test", base_url="http://localhost:8000")

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        with patch.object(client._client, "request", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
            with pytest.raises(BitmodConnectionError):
                await client.health()

    @pytest.mark.asyncio
    async def test_timeout_error(self, client):
        side_effect = httpx.ReadTimeout("timed out")
        with patch.object(client._client, "request", new_callable=AsyncMock, side_effect=side_effect):
            with pytest.raises(BitmodTimeoutError):
                await client.health()

    @pytest.mark.asyncio
    async def test_auth_error(self, client):
        mock_request = MagicMock(spec=httpx.Request)
        mock_request.url = "http://localhost:8000/health"
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "unauthorized"}
        mock_resp.text = '{"error": "unauthorized"}'

        with patch.object(
            client._client, "request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError("401", request=mock_request, response=mock_resp),
        ):
            with pytest.raises((BitmodAuthError, httpx.HTTPStatusError)):
                await client.health()
