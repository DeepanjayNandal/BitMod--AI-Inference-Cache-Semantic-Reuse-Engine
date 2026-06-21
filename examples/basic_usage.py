"""Simplest Bitmod usage: ingest text, query it, print the answer.

Works out of the box with zero config (SQLite backend, brings your own LLM key).
Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or configure Ollama for local inference.
"""
from __future__ import annotations

from bitmod import Bitmod

bm = Bitmod()

bm.ingest("Bitmod is a modular AI data infrastructure with a 9-layer cache engine.", title="Overview")
bm.ingest("Refund requests must be submitted within 30 days of purchase.", title="Policy")

result = bm.query("What is the refund policy?")
print(result.answer)
print(f"Cached: {result.cached}  |  Model: {result.model_used}  |  {result.generation_ms}ms")

# Query again — this time it hits the cache
result2 = bm.query("What is the refund policy?")
print(f"\nSecond query cached: {result2.cached}  |  {result2.generation_ms}ms")

bm.close()
