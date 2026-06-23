"""FastAPI app exposing the RAG pipeline."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.log import configure_logging, get_logger
from src.generation.rag_pipeline import RAGPipeline


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
    logger.info(f"Question received: {req.question[:60]}")
    top_k = req.top_k or settings.top_k
    try:
        result = await app.state.pipeline.answer(req.question, top_k=top_k)
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
    }


@app.post("/ask/stream")
async def ask_stream(req: AskRequest) -> StreamingResponse:
    logger.info(f"Streaming question: {req.question[:60]}")
    top_k = req.top_k or settings.top_k

    async def event_stream():
        try:
            async for token in app.state.pipeline.answer_stream(req.question, top_k=top_k):
                yield token
        except Exception as e:
            logger.exception("Streaming failed")
            yield f"\n[ERROR: {e}]"

    return StreamingResponse(event_stream(), media_type="text/plain")