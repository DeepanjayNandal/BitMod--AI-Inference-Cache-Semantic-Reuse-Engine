"""Cohere embedding adapter — delegates to official SDK."""

from __future__ import annotations

import os

from bitmod.interfaces.embeddings import EmbeddingProvider

try:
    import cohere
except ImportError as e:
    raise ImportError("Cohere embeddings require: pip install bitmod[embeddings-cohere]") from e


class CohereEmbeddingAdapter(EmbeddingProvider):
    def __init__(self, model: str = "embed-v4.0", api_key: str | None = None):
        self._client = cohere.Client(api_key=api_key or os.getenv("COHERE_API_KEY", ""))
        self._model = model

    def embed(self, text: str) -> list[float]:
        response = self._client.embed(texts=[text], model=self._model, input_type="search_document")
        return response.embeddings[0]  # type: ignore[no-any-return]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embed(texts=texts, model=self._model, input_type="search_document")
        return response.embeddings  # type: ignore[no-any-return]

    def dimensions(self) -> int:
        return 1024  # Cohere embed-v4.0 default
