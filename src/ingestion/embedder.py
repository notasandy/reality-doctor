"""Embedding generator using sentence-transformers."""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from src.core.config import settings


EMBEDDING_DIM = 384  # all-MiniLM-L6-v2; update if you switch models


class Embedder:
    """Wraps SentenceTransformer with our preferred defaults."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self.model = SentenceTransformer(self.model_name, device="cpu")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return vectors.tolist()

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]