"""AWS Bedrock LLM adapter — delegates to boto3."""

from __future__ import annotations

import asyncio
import os
import queue
import threading
from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

try:
    import boto3
except ImportError as e:
    raise ImportError("Bedrock adapter requires: pip install bitmod[bedrock]") from e


class BedrockAdapter(LLMProvider):
    def __init__(self, model: str = "anthropic.claude-sonnet-4-20250514-v1:0", region: str | None = None):
        self._model = model
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-runtime", region_name=self._region)

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str = "",
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self._model
        system = []
        msgs = []
        for m in messages:
            if m.role == "system":
                system.append({"text": m.content})
            elif m.role == "tool":
                msgs.append(
                    {
                        "role": "user",
                        "content": [{"toolResult": {"toolUseId": m.tool_call_id, "content": [{"text": m.content}]}}],
                    }
                )
            elif m.tool_calls:
                content = []
                if m.content:
                    content.append({"text": m.content})
                for tc in m.tool_calls:
                    content.append({"toolUse": {"toolUseId": tc["id"], "name": tc["name"], "input": tc["arguments"]}})  # type: ignore[dict-item]
                msgs.append({"role": "assistant", "content": content})
            else:
                msgs.append({"role": m.role, "content": [{"text": m.content}]})

        kwargs: dict = {
            "modelId": model,
            "messages": msgs,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["toolConfig"] = {
                "tools": [
                    {"toolSpec": {"name": t.name, "description": t.description, "inputSchema": {"json": t.parameters}}}
                    for t in tools
                ]
            }

        response = await asyncio.to_thread(self._client.converse, **kwargs)

        content = ""  # type: ignore[assignment]
        tool_calls = []
        for block in response.get("output", {}).get("message", {}).get("content", []):
            if "text" in block:
                content += block["text"]
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_calls.append({"id": tu["toolUseId"], "name": tu["name"], "arguments": tu["input"]})

        usage = response.get("usage", {})
        return LLMResponse(
            content=content,  # type: ignore[arg-type]
            tool_calls=tool_calls if tool_calls else None,
            model=model,
            usage={"input_tokens": usage.get("inputTokens", 0), "output_tokens": usage.get("outputTokens", 0)},
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model = model or self._model
        system = []
        msgs = []
        for m in messages:
            if m.role == "system":
                system.append({"text": m.content})
            else:
                msgs.append({"role": m.role, "content": [{"text": m.content}]})

        kwargs: dict = {
            "modelId": model,
            "messages": msgs,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }
        if system:
            kwargs["system"] = system

        q: queue.Queue = queue.Queue()

        def _stream_in_thread():
            try:
                response = self._client.converse_stream(**kwargs)
                for event in response.get("stream", []):
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"].get("delta", {})
                        if t := delta.get("text"):
                            q.put(t)
            except Exception as exc:
                q.put(exc)
            finally:
                q.put(None)  # sentinel

        thread = threading.Thread(target=_stream_in_thread, daemon=True)
        thread.start()
        while True:
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
