"""xAI (Grok) LLM adapter — thin wrapper over OpenAI-compatible API."""

from __future__ import annotations

from bitmod.adapters.llm_openai_compat import OpenAICompatAdapter

DEFAULT_BASE_URL = "https://api.x.ai/v1"


class XAIAdapter(OpenAICompatAdapter):
    """xAI Grok 3 & 4 via OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "grok-3"):
        super().__init__(base_url=DEFAULT_BASE_URL, api_key=api_key, model=model)
