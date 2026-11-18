"""Phase 2 settings, read from .env (see .env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()  # anthropic | openai | mock
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
_DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini", "mock": "mock"}
LLM_MODEL = os.getenv("LLM_MODEL") or _DEFAULT_MODELS.get(LLM_PROVIDER, "")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

TOP_K = int(os.getenv("TOP_K", "5"))
# Below this top-1 retrieval score we refuse instead of letting the LLM guess.
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.35"))
BASIC_USER = os.getenv("BASIC_USER", "")
BASIC_PASSWORD = os.getenv("BASIC_PASSWORD", "")  # both set => every route except /health needs a login
WARMUP = os.getenv("WARMUP", "true").lower() == "true"
