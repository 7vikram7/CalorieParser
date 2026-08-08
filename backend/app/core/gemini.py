from functools import lru_cache

from google import genai

from app.core.config import settings


@lru_cache
def get_gemini_client() -> genai.Client:
    """Constructed lazily, on first call, not at import time.

    `genai.Client(...)` validates the API key immediately and raises if it's
    empty — building this eagerly at module level would crash the whole app
    on boot whenever GEMINI_API_KEY isn't set yet, taking down every
    unrelated endpoint along with it. Callers only pay that cost when they
    actually hit a route that needs Gemini.
    """
    return genai.Client(api_key=settings.GEMINI_API_KEY)
