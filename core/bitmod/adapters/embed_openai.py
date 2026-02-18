"""OpenAI embedding adapter — delegates to official SDK."""

from __future__ import annotations

import os

from bitmod.interfaces.embeddings import EmbeddingProvider

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError("OpenAI embeddings require: pip install bitmod[openai]") from e


class OpenAIEmbeddingAdapter(EmbeddingProvider):
    DIMENSIONS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072, "text-embedding-ada-002": 1536}

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None):
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY", ""))
        self._model = model
        self._dims = self.DIMENSIONS.get(model, 1536)

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(input=[text], model=self._model)
        return response.data[0].embedding  # type: ignore[no-any-return]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [d.embedding for d in sorted(response.data, key=lambda d: d.index)]

    def dimensions(self) -> int:
        return self._dims
