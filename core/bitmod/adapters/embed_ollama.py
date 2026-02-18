"""Ollama embedding adapter — httpx-based."""

from __future__ import annotations

import os

import httpx

from bitmod.interfaces.embeddings import EmbeddingProvider


class OllamaEmbeddingAdapter(EmbeddingProvider):
    def __init__(self, model: str = "nomic-embed-text", base_url: str | None = None):
        self._model = model
        self._base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")  # type: ignore[union-attr]

    def embed(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]  # type: ignore[no-any-return]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def dimensions(self) -> int:
        return 768  # nomic-embed-text default
