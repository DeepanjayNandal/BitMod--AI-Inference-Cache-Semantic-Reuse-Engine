"""Pinecone vector store adapter — delegates to pinecone-client SDK."""

from __future__ import annotations

import os

from bitmod.interfaces.vectors import VectorResult, VectorStore

try:
    from pinecone import Pinecone
except ImportError as e:
    raise ImportError("Pinecone requires: pip install bitmod[pinecone]") from e


class PineconeAdapter(VectorStore):
    def __init__(self, api_key: str | None = None, index_name: str = "bitmod"):
        self._pc = Pinecone(api_key=api_key or os.getenv("BITMOD_PINECONE_API_KEY", ""))
        self._index_name = index_name
        self._index = None
        self._namespace = os.getenv("BITMOD_PINECONE_NAMESPACE", "default")

    def initialize(self, collection: str, dimensions: int) -> None:
        existing = [idx.name for idx in self._pc.list_indexes()]
        if self._index_name not in existing:
            self._pc.create_index(
                name=self._index_name,
                dimension=dimensions,
                metric="cosine",
                spec={"serverless": {"cloud": "aws", "region": "us-east-1"}},
            )
        self._index = self._pc.Index(self._index_name)

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
        texts: list[str] | None = None,
    ) -> None:
        vectors = []
        for i, (id_, emb) in enumerate(zip(ids, embeddings)):
            meta = metadata[i] if metadata else {}
            if texts:
                meta["text"] = texts[i]
            vectors.append({"id": id_, "values": emb, "metadata": meta})
        self._index.upsert(vectors=vectors, namespace=self._namespace)  # type: ignore[attr-defined]

    def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[VectorResult]:
        kwargs: dict = {
            "vector": embedding,
            "top_k": limit,
            "namespace": self._namespace,
            "include_metadata": True,
        }
        if filters:
            kwargs["filter"] = filters
        results = self._index.query(**kwargs)  # type: ignore[attr-defined]
        return [VectorResult(id=m.id, score=m.score, metadata=m.metadata or {}) for m in results.matches]

    def delete(self, ids: list[str]) -> None:
        self._index.delete(ids=ids, namespace=self._namespace)  # type: ignore[attr-defined]
