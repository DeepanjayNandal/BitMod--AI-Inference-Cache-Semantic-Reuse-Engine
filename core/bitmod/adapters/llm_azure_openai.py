"""Azure OpenAI LLM adapter — delegates to openai SDK with Azure config."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

try:
    from openai import AsyncAzureOpenAI
except ImportError as e:
    raise ImportError("Azure OpenAI adapter requires: pip install bitmod[azure]") from e


class AzureOpenAIAdapter(LLMProvider):
    def __init__(self, model: str = "gpt-4o"):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            timeout=120.0,
            max_retries=2,
        )
        self._model = os.getenv("AZURE_OPENAI_DEPLOYMENT", model)

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
