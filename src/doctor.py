"""Doctor — the full pipeline both the API and the Telegram bot call.

Order: scrub secrets -> deterministic FAQ router (free) -> RAG fallback.
The RAG step already validates any config block (see rag_pipeline.answer).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.generation.rag_pipeline import RAGPipeline
from src.retrieval.qdrant_store import SearchResult
from src.safety import route, scrub


@dataclass
class DoctorReply:
    answer: str
    route: str | None = None        # FAQ rule name if answered deterministically
    used_llm: bool = False          # True only when the LLM was actually called
    valid: bool = True
    notice: str | None = None       # "I removed your key" line, if anything was scrubbed
    sources: list[SearchResult] = field(default_factory=list)


class Doctor:
    """Holds the RAG pipeline (embedder + Qdrant + LLM) and runs the flow."""

    def __init__(self) -> None:
        self.pipeline = RAGPipeline()

    async def diagnose(self, text: str, *, allow_llm: bool = True) -> DoctorReply:
        clean = scrub(text)
        notice = clean.notice()

        # 1. Deterministic fast-path — zero tokens.
        hit = route(clean.text)
        if hit is not None:
            return DoctorReply(answer=hit.answer, route=hit.rule, used_llm=False, notice=notice)

        # 2. Rate-limited caller with no FAQ match — caller decides what to show.
        if not allow_llm:
            return DoctorReply(
                answer="", route=None, used_llm=False, notice=notice, valid=True
            )

        # 3. RAG (validates config blocks internally).
        res = await self.pipeline.answer(clean.text)
        return DoctorReply(
            answer=res.answer,
            route=None,
            used_llm=True,
            valid=res.valid,
            notice=notice,
            sources=res.sources,
        )
