"""OpenAI LLM adapter — delegates to official SDK."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

try:
    from openai import AsyncOpenAI
except ImportError as e:
    raise ImportError("OpenAI adapter requires: pip install bitmod[openai]") from e


class OpenAIAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self._client = AsyncOpenAI(api_key=api_key, timeout=120.0, max_retries=2)
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
        msgs = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = []
            for tc in choice.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            model=response.model,
            usage={"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens}
            if response.usage
            else {},
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model = model or self._model
        msgs = [{"role": m.role, "content": m.content} for m in messages]

        stream = await self._client.chat.completions.create(
            model=model,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
