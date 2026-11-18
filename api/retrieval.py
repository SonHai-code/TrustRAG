"""Dense retrieval from Qdrant (hybrid search + reranking arrive in Phase 3)."""
from dataclasses import dataclass
from functools import lru_cache

from ingestion.config import COLLECTION, QDRANT_API_KEY, QDRANT_URL


class RetrievalError(RuntimeError):
    pass


@dataclass
class Hit:
    score: float
    payload: dict


@lru_cache(maxsize=1)
def _client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)


def warmup() -> None:
    """Load the embedding model once at startup so the first request is not slow."""
    from ingestion.embed import embed_texts
    embed_texts(["khởi động"], show_progress=False)


def count_points() -> int:
    try:
        return _client().count(COLLECTION).count
    except Exception as exc:
        raise RetrievalError(f"Qdrant unavailable or collection missing: {exc}") from exc


def retrieve(question: str, top_k: int = 5) -> list[Hit]:
    """Blocking call (embedding + network): run it in a thread from async code."""
    from ingestion.embed import embed_texts
    try:
        vector = embed_texts([question], show_progress=False)[0]
        points = _client().query_points(COLLECTION, query=vector, limit=top_k, with_payload=True).points
    except Exception as exc:
        raise RetrievalError(f"Qdrant unavailable or collection missing: {exc}") from exc
    return [Hit(score=float(p.score), payload=p.payload or {}) for p in points]
