"""FastAPI app exposing the RAG pipeline."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.log import configure_logging, get_logger
from src.generation.rag_pipeline import RAGPipeline
from src.safety import route, scrub


configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading RAG pipeline...")
    app.state.pipeline = RAGPipeline()
    logger.info("RAG pipeline ready")
    yield
    logger.info("Shutting down")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


@app.get("/health")
async def health() -> dict:
    try:
        app.state.pipeline.store.client.get_collections()
        qdrant_ok = True
    except Exception as e:
        logger.warning(f"Qdrant unreachable: {e}")
        qdrant_ok = False

    status = "ok" if qdrant_ok else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "qdrant": "ok" if qdrant_ok else "unreachable",
    }


@app.post("/ask")
async def ask(req: AskRequest) -> dict:
    # 1. Scrub secrets BEFORE logging or any model call.
    clean = scrub(req.question)
    logger.info(f"Question received (scrubbed): {clean.text[:60]}")

    # 2. Deterministic fast-path — answer known problems with zero LLM tokens.
    hit = route(clean.text)
    if hit is not None:
        logger.info(f"Answered from FAQ router: {hit.rule}")
        return {
            "answer": hit.answer,
            "sources": [],
            "route": hit.rule,
            "redacted": clean.redacted,
            "notice": clean.notice(),
        }

    # 3. Fall through to RAG.
    top_k = req.top_k or settings.top_k
    try:
        result = await app.state.pipeline.answer(clean.text, top_k=top_k)
    except Exception as e:
        logger.exception("Failed to answer question")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "answer": result.answer,
        "sources": [
            {
                "source_file": s.source_file,
                "title": s.title,
                "section": s.section,
                "score": s.score,
            }
            for s in result.sources
        ],
        "route": None,
        "redacted": clean.redacted,
        "notice": clean.notice(),
    }


@app.post("/ask/stream")
async def ask_stream(req: AskRequest) -> StreamingResponse:
    clean = scrub(req.question)
    logger.info(f"Streaming question (scrubbed): {clean.text[:60]}")
    top_k = req.top_k or settings.top_k

    async def event_stream():
        # Tell the user up front if we removed any secrets.
        notice = clean.notice()
        if notice:
            yield notice + "\n\n"

        # Deterministic fast-path: stream the canned answer, no LLM.
        hit = route(clean.text)
        if hit is not None:
            logger.info(f"Answered from FAQ router: {hit.rule}")
            yield hit.answer
            return

        try:
            async for token in app.state.pipeline.answer_stream(clean.text, top_k=top_k):
                yield token
        except Exception as e:
            logger.exception("Streaming failed")
            yield f"\n[ERROR: {e}]"

    return StreamingResponse(event_stream(), media_type="text/plain")