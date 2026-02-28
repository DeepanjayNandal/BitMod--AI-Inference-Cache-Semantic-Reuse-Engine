"""Google Gemini LLM adapter — delegates to official SDK."""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import AsyncIterator

from bitmod.interfaces.llm import LLMMessage, LLMProvider, LLMResponse, ToolDefinition

try:
    import google.generativeai as genai
except ImportError as e:
    raise ImportError("Gemini adapter requires: pip install bitmod[gemini]") from e


class GeminiAdapter(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        if not api_key:
            raise ValueError("Gemini API key is required")
        genai.configure(api_key=api_key)
        self._model_name = model

    def _parse_messages(self, messages: list[LLMMessage]):
        """Parse LLMMessages into Gemini format. Returns (gmodel, history, last_msg)."""
        history = []
        system_instruction = None
        for m in messages:
            if m.role == "system":
                system_instruction = m.content
            elif m.role == "user":
                history.append({"role": "user", "parts": [m.content]})
            elif m.role == "assistant":
                history.append({"role": "model", "parts": [m.content]})

        return system_instruction, history

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str = "",
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model_name = model or self._model_name
        system_instruction, history = self._parse_messages(messages)

        if system_instruction:
            gmodel = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        else:
            gmodel = genai.GenerativeModel(model_name)

        if not history:
            return LLMResponse(
                content="",
                model=model_name,
                usage={"input_tokens": 0, "output_tokens": 0},
            )

        chat = gmodel.start_chat(history=history[:-1] if len(history) > 1 else [])
        last_msg = history[-1]["parts"][0]

        response = await asyncio.to_thread(
            chat.send_message,
            last_msg,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        return LLMResponse(
            content=response.text,
            model=model_name,
            usage={
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
            },
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model_name = model or self._model_name
        system_instruction, history = self._parse_messages(messages)

        if system_instruction:
            gmodel = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        else:
            gmodel = genai.GenerativeModel(model_name)

        if not history:
            return

        chat = gmodel.start_chat(history=history[:-1] if len(history) > 1 else [])
        last_msg = history[-1]["parts"][0]

        q: queue.Queue = queue.Queue()

        def _stream_in_thread():
            try:
                response = chat.send_message(
                    last_msg,
                    generation_config=genai.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                    stream=True,
                )
                for chunk in response:
                    if chunk.text:
                        q.put(chunk.text)
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
