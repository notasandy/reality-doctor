"""End-to-end RAG: question → search → LLM answer."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.generation.llm_client import LLMClient
from src.ingestion.embedder import Embedder
from src.retrieval.qdrant_store import QdrantStore, SearchResult


SYSTEM_PROMPT = """You are a helpful assistant that answers questions about FastAPI \
using only the provided documentation excerpts.

Rules:
- Answer only based on the provided context. If the context doesn't contain enough \
information, say "I don't know based on the provided docs."
- Be concise but complete. Use code examples from the context when relevant.
- At the end of your answer, list the source files you used as a bulleted list under "Sources:".
- Do not invent file paths or APIs that aren't in the context.
"""


@dataclass
class RAGResponse:
    """Result of a non-streaming RAG call."""
    answer: str
    sources: list[SearchResult]


class RAGPipeline:
    """Orchestrates retrieval and generation."""

    def __init__(self) -> None:
        self.embedder = Embedder()
        self.store = QdrantStore()
        self.llm = LLMClient()

    def _retrieve(self, question: str, top_k: int = 5) -> list[SearchResult]:
        query_vector = self.embedder.embed_one(question)
        return self.store.search(query_vector, top_k=top_k)

    def _build_user_prompt(self, question: str, hits: list[SearchResult]) -> str:
        """Format retrieved chunks as context for the LLM."""
        context_blocks = []
        for i, hit in enumerate(hits, start=1):
            context_blocks.append(
                f"[Source {i}: {hit.source_file} - {hit.section}]\n{hit.text}"
            )
        context = "\n\n---\n\n".join(context_blocks)
        return f"Context:\n\n{context}\n\nQuestion: {question}"

    async def answer(self, question: str, top_k: int = 5) -> RAGResponse:
        """Run the full pipeline, return complete answer."""
        hits = self._retrieve(question, top_k=top_k)
        user_prompt = self._build_user_prompt(question, hits)
        answer = await self.llm.generate(SYSTEM_PROMPT, user_prompt)
        return RAGResponse(answer=answer, sources=hits)

    async def answer_stream(
        self,
        question: str,
        top_k: int = 5,
    ) -> AsyncIterator[str]:
        """Run the pipeline, stream the answer token by token.

        Emits the answer text first, then a final block with source metadata.
        """
        hits = self._retrieve(question, top_k=top_k)
        user_prompt = self._build_user_prompt(question, hits)

        async for token in self.llm.stream(SYSTEM_PROMPT, user_prompt):
            yield token