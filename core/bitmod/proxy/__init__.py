"""Multi-format LLM proxy -- drop-in middleware for any AI SDK.

Bitmod intercepts every prompt, runs the 9-layer cache pipeline, and forwards
cache misses to the configured LLM backend. Users change ONE line (base_url)
and get intelligent caching for free.

Supports three API formats natively:

1. OpenAI format (/v1/chat/completions)
2. Anthropic format (/v1/messages)
3. Gemini format (/v1beta/models/{model}:generateContent)
"""

# Re-export everything that was previously importable from bitmod.proxy
from bitmod.proxy.anthropic_format import (
    _anthropic_stream_text,
    _build_anthropic_error,
    _build_anthropic_response,
    _extract_anthropic_user_message,
    _sse,
    handle_anthropic,
    handle_anthropic_stream,
)
from bitmod.proxy.base import (
    _MODEL_PROVIDER_MAP,
    BitmodProxy,
    _CacheResult,
    _detect_provider_from_model,
    _make_router_for_provider,
)
from bitmod.proxy.gemini_format import (
    _build_gemini_error,
    _build_gemini_response,
    _extract_gemini_parts_text,
    _extract_gemini_user_message,
    handle_gemini,
    handle_gemini_stream,
)
from bitmod.proxy.openai_format import (
    _build_openai_response,
    _build_stream_chunk,
    _extract_user_message,
    handle_completion,
    handle_completion_stream,
)

__all__ = [
    "BitmodProxy",
    "_CacheResult",
    "_detect_provider_from_model",
    "_make_router_for_provider",
    "_MODEL_PROVIDER_MAP",
    "_extract_user_message",
    "_build_openai_response",
    "_build_stream_chunk",
    "_extract_anthropic_user_message",
    "_build_anthropic_response",
    "_build_anthropic_error",
    "_sse",
    "_anthropic_stream_text",
    "_extract_gemini_user_message",
    "_extract_gemini_parts_text",
    "_build_gemini_response",
    "_build_gemini_error",
    "handle_completion",
    "handle_completion_stream",
    "handle_anthropic",
    "handle_anthropic_stream",
    "handle_gemini",
    "handle_gemini_stream",
]
