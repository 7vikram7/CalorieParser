import hashlib
import json
import logging

import httpx
from google.genai import errors, types

from app.core.agents import run_meal_estimate_pipeline
from app.core.clients import GEMINI_MODEL, GROQ_MODEL, gemini_client, groq_client
from app.core.config import settings
from app.core.supabase import get_service_role_client
from app.core.usda import search_usda_foods

logger = logging.getLogger(__name__)

ESTIMATE_SYSTEM_PROMPT = """You are a professional nutritionist AI. Given a natural-language
meal description, estimate the nutritional content as accurately as possible.

Be realistic. If the description is vague, estimate conservatively and lower the
confidence score. If you cannot estimate at all, set confidence to 0.0 and explain
in notes."""

GROUNDED_SYSTEM_PROMPT = """You are a professional nutritionist AI. Given a natural-language
meal description, estimate the nutritional content as accurately as possible.

You have access to a tool, search_usda_food, that looks up standardized per-100g
nutrition facts from the USDA FoodData Central database. Use it for less common
foods, branded/packaged items, or anything you are not highly confident about, to
ground your estimate in real data instead of guessing. You may call it more than
once for a multi-item meal. You can skip it for extremely common foods you are
already confident about (e.g. "one banana") - it exists to raise accuracy and
confidence on the cases that need it, not to slow down every request.

Be realistic. If the description is vague, estimate conservatively and lower the
confidence score. If you cannot estimate at all, set confidence to 0.0 and explain
in notes."""

RESULT_JSON_SPEC = """Respond with a single JSON object with exactly these fields:
- name: short descriptive name for the meal/food item
- serving_size_value: numeric amount (e.g. 1.0, 200.0)
- serving_size_unit: unit string (e.g. "serving", "ml", "g", "piece")
- calories: integer total kcal
- protein_g: grams of protein (decimal)
- carbs_g: grams of carbohydrates (decimal)
- fat_g: grams of fat (decimal)
- confidence: float 0.0-1.0 - higher if grounded in real USDA search results,
  lower if estimated from general knowledge alone
- notes: string with any caveats, assumptions, or clarifications (null if none)"""

FINAL_JSON_INSTRUCTION = f"Now give your final answer as JSON.\n\n{RESULT_JSON_SPEC}\n\nOutput only the JSON object, nothing else."

USDA_SEARCH_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_usda_food",
            description=(
                "Search USDA FoodData Central for standardized nutrition facts (per 100g) "
                "for a specific food item."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Simple food name, e.g. 'banana' or 'chicken breast, cooked'",
                    }
                },
                "required": ["query"],
            },
        )
    ]
)

# Gemini's default retry policy (5 attempts, exponential backoff up to 60s
# between them) can turn a single "high demand" 503 into minutes of hanging
# - observed firsthand while building tool use, and tightened once already
# in Phase 3a. Now that a fast, always-available Groq fallback exists
# (estimate_grounded() below), a slow Gemini failure is pure wasted
# latency rather than an accepted tradeoff - tightened further (verified
# live against a real 503: with the old 30s/2-attempt settings, a single
# failing grounded request took 34s before falling back; not tuned before
# because there was nothing faster to fall back to).
_GEMINI_HTTP_OPTIONS = types.HttpOptions(timeout=10_000, retry_options=types.HttpRetryOptions(attempts=1, max_delay=1))


def _is_gemini_unavailable(exc: Exception) -> bool:
    """True for errors that mean 'Gemini isn't usable right now, try Groq
    instead' - quota exhaustion (429/RESOURCE_EXHAUSTED), the model being
    temporarily overloaded (503/UNAVAILABLE), or a *server-returned*
    deadline error (504/DEADLINE_EXCEEDED).

    Also catches httpx.TimeoutException - a distinct case from the 504
    above. 504 is the API responding with an error payload; a
    TimeoutException (ConnectTimeout/ReadTimeout/etc.) is our own client
    giving up before any response arrived at all, per
    _GEMINI_HTTP_OPTIONS's timeout. Confirmed live in production
    (2026-08-14, real user testing): this path is NOT wrapped into
    errors.APIError by the SDK, so the original 429/503/504-only check
    missed it entirely and a slow Gemini call surfaced as a raw 502
    instead of falling back to Groq within the same request.

    Anything else (bad request, auth failure, etc.) is a real bug and
    should surface as-is rather than being masked by a fallback.
    """
    if isinstance(exc, errors.APIError):
        return exc.code in (429, 503, 504)
    return isinstance(exc, httpx.TimeoutException)


async def estimate_simple(description: str) -> dict:
    """Cheap single-call estimate via Groq (JSON mode). No tool use -
    relies on the model's own world knowledge. This is the default path
    for simple descriptions, and also Gemini's fallback when it's
    unavailable, since Groq's quota is entirely separate from Gemini's.

    Almost always one item, but still wrapped as {"items": [...]} - every
    path in this file (estimate_simple, estimate_agentic, _gemini_grounded)
    returns that same shape so foods.py never needs to know which path
    actually served a given request.
    """
    response = groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": f"{ESTIMATE_SYSTEM_PROMPT}\n\n{RESULT_JSON_SPEC}"},
            {"role": "user", "content": f"Estimate the nutrition for: {description}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    item = json.loads(response.choices[0].message.content)
    return {"items": [item]}


async def estimate_agentic(description: str) -> dict:
    """Multi-agent pipeline (Phase 3d) for complex meals: parse into items
    (Groq) -> look each up in USDA (no LLM) -> estimate EACH item
    separately (Groq) -> rules-based validation per item, retrying the
    estimate step with the validation failures fed back as feedback (max
    2 retries) before returning the last attempt regardless. See
    app/core/agents.py for the LangGraph state machine - this is a thin
    async wrapper since the graph itself is invoked synchronously (its
    nodes are all synchronous SDK/API calls, same as the rest of this
    file).
    """
    return {"items": run_meal_estimate_pipeline(description)}


async def estimate_grounded(description: str) -> dict:
    """Complex/multi-item meals go through the agent pipeline first
    (estimate_agentic). If that fails for any reason - a bug, an API
    outage anywhere in its chain, anything - fall back to the older
    single-shot Gemini tool-calling flow, and if that ALSO fails, fall
    back one more time to the plain Groq estimate (no grounding, but
    always available). This endpoint should effectively never 502: worst
    case is an ungrounded estimate, not a failed request. Unexpected
    exceptions are still logged with a full traceback at each layer so a
    real bug stays visible in Render's logs even though it doesn't
    surface as an error response.
    """
    try:
        return await estimate_agentic(description)
    except Exception as e:
        logger.warning("Agent pipeline failed (%s), falling back to Gemini tool-calling flow", e)
        try:
            return await _gemini_grounded(description)
        except Exception as e2:
            if _is_gemini_unavailable(e2):
                logger.warning("Gemini unavailable (%s), falling back to Groq for grounded estimate", e2)
            else:
                logger.exception("Gemini grounded flow also failed unexpectedly, falling back to Groq")
            return await estimate_simple(description)


async def _gemini_grounded(description: str) -> dict:
    client = gemini_client()
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=f"Estimate the nutrition for: {description}")])
    ]

    first = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config={
            "system_instruction": GROUNDED_SYSTEM_PROMPT,
            "tools": [USDA_SEARCH_TOOL],
            "tool_config": {"function_calling_config": {"mode": "AUTO"}},
            "http_options": _GEMINI_HTTP_OPTIONS,
        },
    )
    contents.append(first.candidates[0].content)

    if first.function_calls:
        response_parts = []
        for call in first.function_calls:
            query = call.args.get("query", "") if call.args else ""
            try:
                results = search_usda_foods(settings.USDA_API_KEY, query)
            except Exception:
                logger.exception("USDA lookup failed for query=%r", query)
                results = []
            response_parts.append(types.Part.from_function_response(name=call.name, response={"results": results}))
        contents.append(types.Content(role="user", parts=response_parts))

    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=FINAL_JSON_INSTRUCTION)]))

    final = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config={
            "system_instruction": GROUNDED_SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "http_options": _GEMINI_HTTP_OPTIONS,
        },
    )
    # This fallback-of-a-fallback only fires once the primary agent
    # pipeline has already failed - wrapping its one combined result as a
    # single-item list (rather than teaching this older flow the agent
    # pipeline's per-item schema too) means losing the per-item breakdown
    # only in that already-degraded case, not a regression from before.
    item = json.loads(final.text)
    return {"items": [item]}


def _cache_key(description: str) -> str:
    return hashlib.sha256(description.strip().lower().encode("utf-8")).hexdigest()


def get_cached_estimate(description: str) -> dict | None:
    """Service-role client, not a user-scoped one: estimate_cache has no
    per-user owner (it's a global cache keyed by description hash) and
    /v1/foods/estimate itself has no auth requirement to scope by.
    """
    result = (
        get_service_role_client()
        .table("estimate_cache")
        .select("estimate")
        .eq("description_hash", _cache_key(description))
        .execute()
    )
    return result.data[0]["estimate"] if result.data else None


def set_cached_estimate(description: str, estimate: dict, source: str) -> None:
    try:
        get_service_role_client().table("estimate_cache").upsert(
            {
                "description_hash": _cache_key(description),
                "description": description,
                "estimate": estimate,
                "source": source,
            }
        ).execute()
    except Exception:
        # Caching is a best-effort optimization - a write failure shouldn't
        # fail a request that already has a perfectly good estimate.
        logger.exception("Failed to write estimate_cache row")
