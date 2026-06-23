"""Quick CLI for searching the indexed FastAPI docs.

Usage:
    uv run python -m scripts.search "How do I add authentication?"
"""
from __future__ import annotations

import sys

from src.ingestion.embedder import Embedder
from src.retrieval.qdrant_store import QdrantStore


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.search '<your question>'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    embedder = Embedder()
    store = QdrantStore()

    query_vector = embedder.embed_one(query)
    results = store.search(query_vector, top_k=5)

    print(f"\nQuery: {query}\n")
    print(f"Top {len(results)} results:\n")
    for i, hit in enumerate(results, start=1):
        print(f"--- Result {i} (score: {hit.score:.3f}) ---")
        print(f"File:    {hit.source_file}")
        print(f"Title:   {hit.title}")
        print(f"Section: {hit.section}")
        print(f"Text:    {hit.text[:300]}...")
        print()


if __name__ == "__main__":
    main()