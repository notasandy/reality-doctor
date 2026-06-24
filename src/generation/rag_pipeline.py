"""End-to-end RAG: question → search → LLM answer."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.generation.llm_client import LLMClient
from src.ingestion.embedder import Embedder
from src.retrieval.qdrant_store import QdrantStore, SearchResult
from src.safety.validate import validate_answer


SYSTEM_PROMPT = """You are "Reality Doctor", an assistant that helps users fix self-hosted \
anti-censorship setups (VLESS + Reality, MTProxy, zapret), using ONLY the provided handbook \
excerpts.

Rules:
- Diagnose from the user's message plus the context. Answer ONLY from the context. If the \
context doesn't cover it, say "I don't have that in the handbook" and ask for the specific \
log line or symptom you'd need.
- Prefer the MINIMAL fix: name the exact field, command, or setting to change \
(e.g. "set `flow` to `xtls-rprx-vision` on both server and client"). Do NOT dump a whole \
regenerated config.
- Only include a config block when a snippet is genuinely necessary. When you do, output the \
SMALLEST valid JSON snippet, wrapped in a ```json fence, using placeholders \
(YOUR_UUID, YOUR_PRIVATE_KEY, ...) — never invent real keys, UUIDs, or IPs.
- Do not invent fields, options, or file paths that aren't in the context.
- Never ask the user for, or repeat back, their private keys, UUIDs, or passwords.
- Be concise and technical. End with "Source:" and the handbook section(s) you used.
"""

# Shown instead of a broken answer when the model emits invalid config JSON.
INVALID_CONFIG_FALLBACK = (
    "⚠️ I generated a config block that didn't pass JSON validation, so I'm not showing it — "
    "pasting broken config would stop Xray from starting. Please rephrase your question, or "
    "paste your exact error / `journalctl -u xray` line so I can give a precise, minimal fix."
)


@dataclass
class RAGResponse:
    """Result of a non-streaming RAG call."""
    answer: str
    sources: list[SearchResult]
    valid: bool = True


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
        """Run the full pipeline, validate any config block, return the answer."""
        hits = self._retrieve(question, top_k=top_k)
        user_prompt = self._build_user_prompt(question, hits)
        answer = await self.llm.generate(SYSTEM_PROMPT, user_prompt)

        # Never surface a config block that doesn't parse as JSON.
        result = validate_answer(answer)
        if not result.ok:
            return RAGResponse(answer=INVALID_CONFIG_FALLBACK, sources=hits, valid=False)
        return RAGResponse(answer=answer, sources=hits, valid=True)

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