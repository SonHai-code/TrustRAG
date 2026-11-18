"""Step 4: store chunks + vectors in Qdrant."""
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ingestion.chunker import Chunk
from ingestion.config import COLLECTION, EMBEDDING_DIM, QDRANT_API_KEY, QDRANT_URL
from ingestion.embed import embed_texts


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)


def ensure_collection(client: QdrantClient, recreate: bool = False) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if recreate and COLLECTION in existing:
        client.delete_collection(COLLECTION)
        existing.discard(COLLECTION)
    if COLLECTION not in existing:
        client.create_collection(
            COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def upsert_chunks(chunks: list[Chunk], batch: int = 64, recreate: bool = False) -> int:
    client = get_client()
    ensure_collection(client, recreate=recreate)
    for i in range(0, len(chunks), batch):
        part = chunks[i:i + batch]
        vectors = embed_texts([c.text for c in part])
        points = [
            PointStruct(
                # deterministic id => re-running ingestion updates instead of duplicating
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c.doc_name}|{c.article}|{c.clause}|{c.part}")),
                vector=v,
                payload=c.as_payload(),
            )
            for c, v in zip(part, vectors)
        ]
        client.upsert(COLLECTION, points=points)
    return len(chunks)


def search(query: str, top_k: int = 5):
    client = get_client()
    qv = embed_texts([query])[0]
    return client.query_points(COLLECTION, query=qv, limit=top_k, with_payload=True).points
