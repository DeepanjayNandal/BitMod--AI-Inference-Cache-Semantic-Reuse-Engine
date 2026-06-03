"""Hugging Face Inference API LLM adapter — delegates to huggingface_hub SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

try:
    from huggingface_hub import AsyncInferenceClient
except ImportError as e:
    raise ImportError("Hugging Face adapter requires: pip install bitmod[huggingface]") from e


class HuggingFaceAdapter(LLMProvider):
    """Hugging Face Inference API via huggingface_hub SDK."""

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.1-70B-Instruct"):
        self._client = AsyncInferenceClient(token=api_key)
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
            "temperature": temperature or 0.01,  # HF API rejects temperature=0
        }
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
            import json

            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
                    if isinstance(tc.function.arguments, str)
                    else tc.function.arguments,
                }
                for tc in choice.message.tool_calls
            ]

        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            model=model,
            usage={
                "input_tokens": getattr(usage, "prompt_tokens", 0),
                "output_tokens": getattr(usage, "completion_tokens", 0),
            },
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
            temperature=temperature or 0.01,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
