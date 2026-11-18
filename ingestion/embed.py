"""Step 3: text -> vectors (multilingual model, works well for Vietnamese)."""
from functools import lru_cache

from ingestion.config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str], batch_size: int = 16, show_progress: bool = True) -> list[list[float]]:
    vectors = get_model().encode(
        texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=show_progress
    )
    return vectors.tolist()
