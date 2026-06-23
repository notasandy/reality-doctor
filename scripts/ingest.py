"""End-to-end ingestion script.

Reads all .md files from data/raw, chunks them, generates embeddings,
and loads everything into Qdrant.

Usage:
    uv run python scripts/ingest.py
"""
from __future__ import annotations

from pathlib import Path

from src.ingestion.chunker import chunk_markdown_file, Chunk
from src.ingestion.embedder import Embedder
from src.retrieval.qdrant_store import QdrantStore

DATA_DIR = Path("data/raw")
BATCH_SIZE = 64


def collect_chunks(data_dir: Path) -> list[Chunk]:
    """Walk data_dir and chunk every .md file."""
    md_files = sorted(data_dir.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")

    all_chunks: list[Chunk] = []
    for path in md_files:
        # Override source_file with a clean relative path
        chunks = chunk_markdown_file(path)
        for c in chunks:
            c.source_file = str(path.relative_to(data_dir))
        all_chunks.extend(chunks)

    print(f"Produced {len(all_chunks)} chunks")
    return all_chunks


def embed_and_store(chunks: list[Chunk]) -> None:
    """Embed all chunks in batches and upsert to Qdrant."""
    embedder = Embedder()
    store = QdrantStore()

    print("Recreating Qdrant collection...")
    store.recreate_collection()

    print(f"Embedding and storing {len(chunks)} chunks (batch size {BATCH_SIZE})...")
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        texts = [c.embedding_text for c in batch]
        vectors = embedder.embed(texts)
        store.upsert_chunks(batch, vectors)
        print(f"  Processed {start + len(batch)}/{len(chunks)}")

    print("Done.")


def main() -> None:
    chunks = collect_chunks(DATA_DIR)
    embed_and_store(chunks)


if __name__ == "__main__":
    main()