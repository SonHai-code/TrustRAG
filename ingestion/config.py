"""Central settings, read from .env (see .env.example)."""
import os
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")  # needed for Qdrant Cloud, empty for local Docker
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# Chunking limits (characters; roughly 4 chars ~ 1 token for Vietnamese is a safe guess)
MAX_CHUNK_CHARS = 2000
