"""Embedding provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers.

    Implementations: Sentence Transformers (local), OpenAI, Cohere, Ollama.
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text string. Returns a float vector."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of float vectors."""

    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of the embedding model."""
