"""Anthropic (Claude) LLM adapter — delegates to official SDK."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError as e:
    raise ImportError("Anthropic adapter requires: pip install bitmod[anthropic]") from e


class AnthropicAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        if not api_key:
            raise ValueError("Anthropic API key is required")
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=120.0,
            max_retries=2,
        )
        self._model = model

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str = "",
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self._model
        system = None
        msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            elif m.role == "tool":
                msgs.append(
                    {
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}],
                    }
                )
            elif m.tool_calls:
                content = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]})
                msgs.append({"role": "assistant", "content": content})
            else:
                msgs.append({"role": m.role, "content": m.content})

        kwargs: dict = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools
            ]

        response = await self._client.messages.create(**kwargs)

        content = ""  # type: ignore[assignment]
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "arguments": block.input})

        return LLMResponse(
            content=content,  # type: ignore[arg-type]
            tool_calls=tool_calls if tool_calls else None,
            model=response.model,
            usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model = model or self._model
        system = None
        msgs = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                msgs.append({"role": m.role, "content": m.content})

        kwargs: dict = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
