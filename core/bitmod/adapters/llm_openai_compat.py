"""OpenAI-compatible LLM adapter — httpx-based, works with any OpenAI-compatible API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition


class OpenAICompatAdapter(LLMProvider):
    """Works with Groq, Mistral, Together, Fireworks, vLLM, LM Studio, etc."""

    def __init__(self, base_url: str, api_key: str = "", model: str = ""):
        if not base_url:
            raise ValueError("base_url is required for OpenAI-compatible adapter")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        # Validate URL scheme
        from urllib.parse import urlparse

        parsed = urlparse(self._base_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("base_url must use http or https scheme")

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str = "",
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self._model
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self._base_url}/chat/completions", json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        tool_calls = None
        if choice["message"].get("tool_calls"):
            tool_calls = []
            for tc in choice["message"]["tool_calls"]:
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"id": tc["id"], "name": tc["function"]["name"], "arguments": args})

        usage = data.get("usage", {})
        return LLMResponse(
            content=choice["message"].get("content", ""),
            tool_calls=tool_calls,
            model=data.get("model", model),
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model = model or self._model
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", f"{self._base_url}/chat/completions", json=payload, headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if content := delta.get("content"):
                            yield content
