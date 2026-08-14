from functools import lru_cache

from google import genai
from groq import Groq

from app.core.config import settings

GROQ_MODEL = "llama-3.3-70b-versatile"
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
