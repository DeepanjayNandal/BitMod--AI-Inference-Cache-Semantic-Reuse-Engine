"""Local embedding adapter — Sentence Transformers."""

from __future__ import annotations

from bitmod.interfaces.embeddings import EmbeddingProvider

try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    raise ImportError("Local embeddings require: pip install bitmod[embeddings-local]") from e


class LocalEmbeddingAdapter(EmbeddingProvider):
    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2", device: str = "cpu"):
        self._model = SentenceTransformer(model, device=device)
        self._dimensions = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()  # type: ignore[no-any-return]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [e.tolist() for e in embeddings]

    def dimensions(self) -> int:
        return self._dimensions  # type: ignore[no-any-return]
