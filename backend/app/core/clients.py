from functools import lru_cache

from google import genai
from groq import Groq

from app.core.config import settings

# llama-3.3-70b-versatile (the original Phase 3b choice) was removed from
# Groq's lineup entirely without warning sometime between 2026-08-14 and
# 2026-08-18 - not deprecated-with-notice, just gone (confirmed via a live
# /v1/models call: not present at all, and a chat.completions.create call
# against it now 404s with "model_not_found"). Replaced with
# openai/gpt-oss-120b after live-testing it against the same JSON-mode
# nutrition-estimate prompt used here: same latency (~0.7s) as the smaller
# openai/gpt-oss-20b and qwen/qwen3.6-27b alternatives, but consistently
# higher self-reported confidence on the same inputs, and effectively free
# at this project's volume ($0.15/1M input + $0.60/1M output tokens - a
# single estimate call is a few hundred tokens).
GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-flash-latest"


@lru_cache
def gemini_client() -> genai.Client:
    """Constructed lazily, on first call, not at import time - `genai.Client(...)`
    validates the API key immediately and would crash the whole app on boot if
    GEMINI_API_KEY isn't set yet."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)


@lru_cache
def groq_client() -> Groq:
    return Groq(api_key=settings.GROQ_API_KEY)
