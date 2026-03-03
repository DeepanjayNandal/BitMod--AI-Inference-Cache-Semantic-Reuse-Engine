"""Qdrant vector store adapter — delegates to qdrant-client SDK."""

from __future__ import annotations

from bitmod.interfaces.vectors import VectorResult, VectorStore

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointIdsList,
        PointStruct,
        VectorParams,
    )
except ImportError as e:
    raise ImportError("Qdrant requires: pip install bitmod[qdrant]") from e


class QdrantAdapter(VectorStore):
    def __init__(self, url: str = "http://localhost:6333", api_key: str | None = None):
        kwargs: dict = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        self._client = QdrantClient(**kwargs)
        self._collection = ""

    def initialize(self, collection: str, dimensions: int) -> None:
        self._collection = collection
        collections = [c.name for c in self._client.get_collections().collections]
        if collection not in collections:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
            )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
        texts: list[str] | None = None,
    ) -> None:
        points = []
        for i, (id_, emb) in enumerate(zip(ids, embeddings)):
            payload = metadata[i] if metadata else {}
            if texts:
                payload["text"] = texts[i]
            points.append(PointStruct(id=id_, vector=emb, payload=payload))
        self._client.upsert(collection_name=self._collection, points=points)

    def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[VectorResult]:
        query_filter = None
        if filters:
            conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()]
            query_filter = Filter(must=conditions)

        results = self._client.search(
            collection_name=self._collection,
            query_vector=embedding,
            limit=limit,
            query_filter=query_filter,
        )
        return [VectorResult(id=str(r.id), score=r.score, metadata=r.payload or {}) for r in results]

    def delete(self, ids: list[str]) -> None:
        self._client.delete(collection_name=self._collection, points_selector=PointIdsList(points=ids))
