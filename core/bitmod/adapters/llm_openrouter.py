"""OpenRouter LLM adapter — thin wrapper over OpenAI-compatible API."""

from __future__ import annotations

from bitmod.adapters.llm_openai_compat import OpenAICompatAdapter

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(OpenAICompatAdapter):
    """OpenRouter unified gateway via OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "anthropic/claude-sonnet-4"):
        super().__init__(base_url=DEFAULT_BASE_URL, api_key=api_key, model=model)
