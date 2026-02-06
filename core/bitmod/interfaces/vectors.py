"""Vector store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VectorResult:
    id: str
    score: float
    metadata: dict


class VectorStore(ABC):
    """Abstract interface for dedicated vector stores.

    Implementations: ChromaDB, Qdrant, Pinecone.
    Optional — the database backend provides built-in vector search by default.
    """

    @abstractmethod
    def initialize(self, collection: str, dimensions: int) -> None:
        """Create or connect to a collection/index."""

    @abstractmethod
    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
        texts: list[str] | None = None,
    ) -> None:
        """Insert or update vectors."""

    @abstractmethod
    def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[VectorResult]:
        """Search for nearest neighbors."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Delete vectors by ID."""
