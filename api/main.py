"""FastAPI app.   Run:  uvicorn api.main:app --reload --port 8000   (docs at /docs)"""
import base64
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from api import rag, settings
from api.llm import LLMConfigError, LLMError
from api.retrieval import RetrievalError
from api.schemas import ChatRequest, ChatResponse, SearchResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.WARMUP:
        import asyncio
        from api.retrieval import warmup
        await asyncio.to_thread(warmup)
    yield


app = FastAPI(title="TrustRAG", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """Optional password wall so a public URL cannot burn your LLM budget (real auth: Phase 7)."""
    if not (settings.BASIC_USER and settings.BASIC_PASSWORD) or request.url.path == "/health":
        return await call_next(request)
    ok = False
    header = request.headers.get("authorization", "")
    if header.lower().startswith("basic "):
        try:
            user, _, password = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            ok = secrets.compare_digest(user.encode(), settings.BASIC_USER.encode()) and secrets.compare_digest(
                password.encode(), settings.BASIC_PASSWORD.encode()
            )
        except Exception:
            ok = False
    if not ok:
        return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="TrustRAG"'})
    return await call_next(request)


@app.exception_handler(RetrievalError)
async def _retrieval_error(_, exc: RetrievalError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(LLMConfigError)
async def _llm_config_error(_, exc: LLMConfigError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def _llm_error(_, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER, "model": settings.LLM_MODEL}


@app.get("/health/ready")
async def ready():
    import asyncio
    from api.retrieval import count_points
    return {"status": "ready", "points": await asyncio.to_thread(count_points)}


@app.post("/search", response_model=SearchResponse)
async def search(req: ChatRequest):
    """Retrieval only (no LLM): useful for debugging and for the baseline metrics."""
    t0 = time.perf_counter()
    hits = await rag.retrieve_hits(req.question, req.top_k)
    return SearchResponse(
        query=req.question,
        results=[rag.to_citation(i, h) for i, h in enumerate(hits, 1)],
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    return await rag.answer(req.question, req.top_k)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def events():
        try:
            async for name, data in rag.answer_stream(req.question, req.top_k):
                yield _sse(name, data)
        except (RetrievalError, LLMError) as exc:  # headers are already sent: report in-band
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Serve the built React app (only when ui/dist exists, i.e. inside the Azure image).
# Mounted last, so every API route above keeps priority.
_UI_DIR = Path(os.getenv("UI_DIST", "ui/dist"))
if _UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_UI_DIR, html=True), name="ui")
