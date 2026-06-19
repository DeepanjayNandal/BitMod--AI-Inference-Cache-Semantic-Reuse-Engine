"""Tests for the universal OpenAI-compatible LLM adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bitmod.adapters.llm_openai_compat import OpenAICompatAdapter
from bitmod.interfaces.llm import LLMMessage, ToolDefinition


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructor:
    """Validate constructor argument handling."""

    def test_requires_base_url(self):
        with pytest.raises(ValueError, match="base_url is required"):
            OpenAICompatAdapter(base_url="")

    def test_validates_http_scheme(self):
        adapter = OpenAICompatAdapter(base_url="http://localhost:8080")
        assert adapter._base_url == "http://localhost:8080"

    def test_validates_https_scheme(self):
        adapter = OpenAICompatAdapter(base_url="https://api.example.com")
        assert adapter._base_url == "https://api.example.com"

    def test_rejects_invalid_scheme(self):
        with pytest.raises(ValueError, match="http or https"):
            OpenAICompatAdapter(base_url="ftp://example.com")

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="http or https"):
            OpenAICompatAdapter(base_url="example.com/v1")

    def test_strips_trailing_slash(self):
        adapter = OpenAICompatAdapter(base_url="http://localhost:8080/")
        assert adapter._base_url == "http://localhost:8080"

    def test_stores_api_key(self):
        adapter = OpenAICompatAdapter(base_url="http://localhost", api_key="sk-test")
        assert adapter._api_key == "sk-test"

    def test_stores_model(self):
        adapter = OpenAICompatAdapter(base_url="http://localhost", model="llama-3")
        assert adapter._model == "llama-3"


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestHeaders:
    """Verify Authorization header presence/absence."""

    def test_includes_auth_header_when_api_key_set(self):
        adapter = OpenAICompatAdapter(base_url="http://localhost", api_key="sk-123")
        headers = adapter._headers()
        assert headers["Authorization"] == "Bearer sk-123"
        assert headers["Content-Type"] == "application/json"

    def test_omits_auth_header_when_no_api_key(self):
        adapter = OpenAICompatAdapter(base_url="http://localhost", api_key="")
        headers = adapter._headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


class TestGenerate:
    """Test generate() request construction and response parsing."""

    @pytest.fixture
    def adapter(self):
        return OpenAICompatAdapter(
            base_url="http://localhost:8080", api_key="test-key", model="default-model"
        )

    def _mock_response(self, content="Hello!", tool_calls=None, model="test-model"):
        """Build a mock httpx.Response matching OpenAI chat completions format."""
        message = {"content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        data = {
            "choices": [{"message": message}],
            "model": model,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        resp = MagicMock(spec=httpx.Response)
        resp.json.return_value = data
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_constructs_correct_payload(self, adapter):
        """Verify the JSON payload sent to the completions endpoint."""
        mock_resp = self._mock_response()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            messages = [LLMMessage(role="user", content="Hi")]
            result = await adapter.generate(messages, model="gpt-4o", temperature=0.7, max_tokens=512)

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "gpt-4o"
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 512
        assert "stream" not in payload

    @pytest.mark.asyncio
    async def test_uses_default_model(self, adapter):
        """When no model is passed to generate(), the constructor default is used."""
        mock_resp = self._mock_response()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            await adapter.generate([LLMMessage(role="user", content="Hi")])

        payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert payload["model"] == "default-model"

    @pytest.mark.asyncio
    async def test_includes_auth_header(self, adapter):
        """Authorization header is sent with the request."""
        mock_resp = self._mock_response()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            await adapter.generate([LLMMessage(role="user", content="Hi")])

        headers = mock_client.post.call_args.kwargs.get("headers") or mock_client.post.call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_parses_response(self, adapter):
        """Response is parsed into LLMResponse with content, model, usage."""
        mock_resp = self._mock_response(content="World", model="gpt-4o")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.generate([LLMMessage(role="user", content="Hi")])

        assert result.content == "World"
        assert result.model == "gpt-4o"
        assert result.usage["input_tokens"] == 10
        assert result.usage["output_tokens"] == 5
        assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_handles_tool_calls(self, adapter):
        """Tool calls in the response are parsed correctly."""
        tool_calls_data = [
            {
                "id": "call_1",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"city": "NYC"}',
                },
            }
        ]
        mock_resp = self._mock_response(content="", tool_calls=tool_calls_data)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.generate([LLMMessage(role="user", content="weather?")])

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "get_weather"
        assert result.tool_calls[0]["arguments"] == {"city": "NYC"}
        assert result.tool_calls[0]["id"] == "call_1"

    @pytest.mark.asyncio
    async def test_includes_tools_in_payload(self, adapter):
        """When tools are provided, they are serialized in the request payload."""
        mock_resp = self._mock_response()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        tools = [
            ToolDefinition(
                name="search",
                description="Search the web",
                parameters={"type": "object", "properties": {"q": {"type": "string"}}},
            )
        ]

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            await adapter.generate([LLMMessage(role="user", content="Hi")], tools=tools)

        payload = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert "tools" in payload
        assert payload["tools"][0]["type"] == "function"
        assert payload["tools"][0]["function"]["name"] == "search"

    @pytest.mark.asyncio
    async def test_http_error_raises(self, adapter):
        """HTTP 500 response raises httpx.HTTPStatusError."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_resp
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await adapter.generate([LLMMessage(role="user", content="Hi")])


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------


class TestStream:
    """Test SSE streaming response parsing."""

    @pytest.mark.asyncio
    async def test_yields_content_chunks(self):
        """stream() yields content deltas from SSE data lines."""
        adapter = OpenAICompatAdapter(base_url="http://localhost", model="test")

        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = mock_aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            chunks = []
            async for chunk in adapter.stream([LLMMessage(role="user", content="Hi")]):
                chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_skips_empty_deltas(self):
        """Lines with no content delta are skipped."""
        adapter = OpenAICompatAdapter(base_url="http://localhost", model="test")

        lines = [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"ok"}}]}',
            "data: [DONE]",
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = mock_aiter_lines
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("bitmod.adapters.llm_openai_compat.httpx.AsyncClient", return_value=mock_client):
            chunks = []
            async for chunk in adapter.stream([LLMMessage(role="user", content="Hi")]):
                chunks.append(chunk)

        assert chunks == ["ok"]
