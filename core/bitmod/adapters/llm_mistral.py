"""Mistral LLM adapter — delegates to official mistralai SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

try:
    from mistralai import Mistral
except ImportError as e:
    raise ImportError("Mistral adapter requires: pip install bitmod[mistral]") from e


class MistralAdapter(LLMProvider):
    """Mistral Large & Codestral via official SDK."""

    def __init__(self, api_key: str, model: str = "mistral-large-latest"):
        self._client = Mistral(api_key=api_key)
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

        kwargs: dict = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]

        response = await self._client.chat.complete_async(**kwargs)
        choice = response.choices[0]

        tool_calls = None
        if choice.message.tool_calls:
            import json

            tool_calls = []
            for tc in choice.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})

        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            model=response.model,
            usage={"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens},
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

        response = await self._client.chat.stream_async(
            model=model,
            messages=msgs,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        async for event in response:
            if event.data.choices and event.data.choices[0].delta.content:
                yield event.data.choices[0].delta.content
