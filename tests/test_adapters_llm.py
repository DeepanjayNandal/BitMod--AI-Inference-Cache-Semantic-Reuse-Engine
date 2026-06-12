"""Tests for LLM adapter implementations using mocked SDK/HTTP calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_msg(text: str) -> list[LLMMessage]:
    return [LLMMessage(role="user", content=text)]


def _system_and_user(system: str, user: str) -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------


class TestAnthropicAdapter:
    """Tests for the Anthropic (Claude) adapter."""

    @pytest.fixture
    def _mock_sdk(self):
        """Patch the anthropic module so the adapter can be imported without a real SDK."""
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_module}):
            yield mock_module

    @pytest.fixture
    def adapter(self, _mock_sdk):
        from bitmod.adapters.llm_anthropic import AnthropicAdapter

        return AnthropicAdapter(api_key="sk-test-key", model="claude-sonnet-4-20250514")

    def test_implements_llm_provider(self, adapter):
        assert isinstance(adapter, LLMProvider)

    @pytest.mark.asyncio
    async def test_generate_constructs_correct_request(self, adapter, _mock_sdk):
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Hello from Claude"

        mock_response = MagicMock()
        mock_response.content = [text_block]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        adapter._client.messages.create = AsyncMock(return_value=mock_response)

        result = await adapter.generate(
            messages=_system_and_user("You are helpful.", "Hi"),
            temperature=0.5,
            max_tokens=1024,
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from Claude"
        assert result.usage["input_tokens"] == 10
        assert result.usage["output_tokens"] == 5

        call_kwargs = adapter._client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["system"] == "You are helpful."
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 1024
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_handles_api_error(self, adapter, _mock_sdk):
        adapter._client.messages.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )

        with pytest.raises(Exception, match="rate limit"):
            await adapter.generate(messages=_user_msg("Hi"))

    def test_rejects_empty_api_key(self, _mock_sdk):
        from bitmod.adapters.llm_anthropic import AnthropicAdapter

        with pytest.raises(ValueError, match="API key is required"):
            AnthropicAdapter(api_key="")

    @pytest.mark.asyncio
    async def test_generate_with_tool_calls(self, adapter, _mock_sdk):
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "call_123"
        tool_block.name = "get_weather"
        tool_block.input = {"city": "NYC"}

        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 8

        adapter._client.messages.create = AsyncMock(return_value=mock_response)

        result = await adapter.generate(messages=_user_msg("What is the weather?"))

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "get_weather"
        assert result.tool_calls[0]["arguments"] == {"city": "NYC"}


# ---------------------------------------------------------------------------
# OpenAI adapter
# ---------------------------------------------------------------------------


class TestOpenAIAdapter:
    """Tests for the OpenAI adapter."""

    @pytest.fixture
    def _mock_sdk(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_module}):
            yield mock_module

    @pytest.fixture
    def adapter(self, _mock_sdk):
        from bitmod.adapters.llm_openai import OpenAIAdapter

        return OpenAIAdapter(api_key="sk-test-key", model="gpt-4o")

    def test_implements_llm_provider(self, adapter):
        assert isinstance(adapter, LLMProvider)

    @pytest.mark.asyncio
    async def test_generate_constructs_correct_request(self, adapter, _mock_sdk):
        mock_message = MagicMock()
        mock_message.content = "Hello from GPT"
        mock_message.tool_calls = None

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 12
        mock_usage.completion_tokens = 7

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = mock_usage

        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await adapter.generate(
            messages=_user_msg("Hi"),
            temperature=0.7,
            max_tokens=2048,
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from GPT"
        assert result.usage["input_tokens"] == 12
        assert result.usage["output_tokens"] == 7

        call_kwargs = adapter._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_generate_handles_api_error(self, adapter, _mock_sdk):
        adapter._client.chat.completions.create = AsyncMock(
            side_effect=Exception("Insufficient quota")
        )

        with pytest.raises(Exception, match="Insufficient quota"):
            await adapter.generate(messages=_user_msg("Hi"))

    def test_rejects_empty_api_key(self, _mock_sdk):
        from bitmod.adapters.llm_openai import OpenAIAdapter

        with pytest.raises(ValueError, match="API key is required"):
            OpenAIAdapter(api_key="")

    @pytest.mark.asyncio
    async def test_generate_with_tool_calls(self, adapter, _mock_sdk):
        mock_tc = MagicMock()
        mock_tc.id = "call_abc"
        mock_tc.function.name = "search"
        mock_tc.function.arguments = '{"query": "test"}'

        mock_message = MagicMock()
        mock_message.content = ""
        mock_message.tool_calls = [mock_tc]

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        adapter._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await adapter.generate(messages=_user_msg("Search for test"))

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search"
        assert result.tool_calls[0]["arguments"] == {"query": "test"}


# ---------------------------------------------------------------------------
# Ollama adapter
# ---------------------------------------------------------------------------


class TestOllamaAdapter:
    """Tests for the Ollama adapter (httpx-based, no SDK)."""

    @pytest.fixture
    def adapter(self):
        from bitmod.adapters.llm_ollama import OllamaAdapter

        return OllamaAdapter(base_url="http://localhost:11434", model="llama3.2")

    def test_implements_llm_provider(self, adapter):
        assert isinstance(adapter, LLMProvider)

    @pytest.mark.asyncio
    async def test_generate_constructs_correct_request(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Hello from Ollama"},
            "model": "llama3.2",
            "prompt_eval_count": 8,
            "eval_count": 4,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await adapter.generate(
                messages=_user_msg("Hi"),
                temperature=0.3,
                max_tokens=512,
            )

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello from Ollama"
        assert result.usage["input_tokens"] == 8
        assert result.usage["output_tokens"] == 4

        call_args = mock_client.post.call_args
        assert "/api/chat" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["model"] == "llama3.2"
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0.3
        assert payload["options"]["num_predict"] == 512

    @pytest.mark.asyncio
    async def test_generate_handles_connection_error(self, adapter):
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with pytest.raises(ConnectionError, match="Connection refused"):
                await adapter.generate(messages=_user_msg("Hi"))

    def test_rejects_invalid_scheme(self):
        from bitmod.adapters.llm_ollama import OllamaAdapter

        with pytest.raises(ValueError, match="http or https"):
            OllamaAdapter(base_url="ftp://localhost:11434")

    @pytest.mark.asyncio
    async def test_generate_handles_http_error(self, adapter):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await adapter.generate(messages=_user_msg("Hi"))
