"""ChromaDB vector store adapter — delegates to chromadb SDK."""

from __future__ import annotations

from bitmod.interfaces.vectors import VectorResult, VectorStore

try:
    import chromadb
except ImportError as e:
    raise ImportError("ChromaDB requires: pip install bitmod[chroma]") from e


class ChromaAdapter(VectorStore):
    def __init__(self, path: str | None = None):
        if path:
            self._client = chromadb.PersistentClient(path=path)
        else:
            self._client = chromadb.Client()
        self._collection = None

    def initialize(self, collection: str, dimensions: int) -> None:
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
        texts: list[str] | None = None,
    ) -> None:
        kwargs: dict = {"ids": ids, "embeddings": embeddings}
        if metadata:
            kwargs["metadatas"] = metadata
        if texts:
            kwargs["documents"] = texts
        self._collection.upsert(**kwargs)  # type: ignore[attr-defined]

    def search(
        self,
        embedding: list[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[VectorResult]:
        kwargs: dict = {"query_embeddings": [embedding], "n_results": limit}
        if filters:
            kwargs["where"] = filters
        results = self._collection.query(**kwargs)  # type: ignore[attr-defined]
        out = []
        for i, id_ in enumerate(results["ids"][0]):
            out.append(
                VectorResult(
                    id=id_,
                    score=1 - results["distances"][0][i] if results.get("distances") else 0,
                    metadata=results["metadatas"][0][i] if results.get("metadatas") else {},
                )
            )
        return out

    def delete(self, ids: list[str]) -> None:
        self._collection.delete(ids=ids)  # type: ignore[attr-defined]
