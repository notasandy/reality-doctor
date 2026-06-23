"""Qdrant vector store wrapper."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.core.config import settings
from src.ingestion.chunker import Chunk
from src.ingestion.embedder import EMBEDDING_DIM


@dataclass
class SearchResult:
    """One search hit from Qdrant."""
    score: float
    text: str
    source_file: str
    title: str
    section: str


class QdrantStore:
    """Thin wrapper around qdrant-client for our use case."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection: str | None = None,
    ) -> None:
        self.client = QdrantClient(
            host=host or settings.qdrant_host,
            port=port or settings.qdrant_port,
        )
        self.collection = collection or settings.qdrant_collection

    def recreate_collection(self) -> None:
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.DOT,
            ),
        )

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks ({len(chunks)}) and vectors ({len(vectors)}) length mismatch"
            )

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": chunk.text,
                    "source_file": chunk.source_file,
                    "title": chunk.title,
                    "section": chunk.section,
                    "chunk_index": chunk.chunk_index,
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        hits = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=top_k,
        ).points

        return [
            SearchResult(
                score=hit.score,
                text=hit.payload["text"],
                source_file=hit.payload["source_file"],
                title=hit.payload["title"],
                section=hit.payload["section"],
            )
            for hit in hits
        ]