import json
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from google.genai import types
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.core.config import settings
from app.core.gemini import get_gemini_client
from app.core.pagination import Pagination, pagination
from app.core.rate_limit import estimate_rate_limit, limiter
from app.core.usda import search_usda_foods
from app.models.estimation import FoodEstimateRequest, FoodEstimateResponse, NutritionalEstimate
from app.models.food import UserCustomFoodCreate, UserCustomFoodResponse
from app.models.user import UserResponse

router = APIRouter(prefix="/foods", tags=["foods"])
logger = logging.getLogger(__name__)

ESTIMATE_SYSTEM_PROMPT = """You are a professional nutritionist AI. Given a natural-language
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

FINAL_JSON_INSTRUCTION = """Now give your final answer as a single JSON object with
exactly these fields:
- name: short descriptive name for the meal/food item
- serving_size_value: numeric amount (e.g. 1.0, 200.0)
- serving_size_unit: unit string (e.g. "serving", "ml", "g", "piece")
- calories: integer total kcal
- protein_g: grams of protein (decimal)
- carbs_g: grams of carbohydrates (decimal)
- fat_g: grams of fat (decimal)
- confidence: float 0.0-1.0 - higher if grounded in real USDA search results,
  lower if estimated from general knowledge alone
- notes: string with any caveats, assumptions, or clarifications (null if none)

Output only the JSON object, nothing else."""

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
# - observed firsthand while building this. Tightened so a persistent
# outage fails in well under a minute per call instead.
_HTTP_OPTIONS = types.HttpOptions(timeout=30_000, retry_options=types.HttpRetryOptions(attempts=2, max_delay=3))


def _needs_grounding(description: str) -> bool:
    """Whether this description is worth the USDA-tool-augmented two-call
    flow, versus the original single-call estimate.

    This exists because of a discovery made while building tool use: the
    Gemini free tier's real binding constraint (revealed by a 429 response,
    not documented anywhere beforehand) is
    GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20 requests/day for
    gemini-3.7-flash (what gemini-flash-latest currently resolves to) - not
    the "15 RPM, 1M tokens/day" this project's docs previously assumed. The
    tool-augmented flow costs 2 Gemini calls per estimate instead of 1;
    applying it unconditionally would roughly halve the app's entire daily
    capacity for its core feature. So: keep the cheap 1-call path for
    obviously-simple descriptions, and reserve the 2-call grounded path for
    ones actually likely to benefit - multi-item meals, or descriptions long
    enough that guessing without a lookup is more likely to be wrong. This
    is a minimal pull-forward of the Phase 3b router concept
    (docs/agent-architecture-plan.md), justified specifically by this quota
    finding rather than being full routing/caching.
    """
    word_count = len(description.split())
    return word_count > 8 or "," in description or " and " in description.lower()


async def _estimate_simple(client, payload: FoodEstimateRequest) -> dict:
    """Original single-call flow: no tool, structured JSON directly."""
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=f"Estimate the nutrition for: {payload.description}",
        config={
            "system_instruction": ESTIMATE_SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "http_options": _HTTP_OPTIONS,
        },
    )
    return json.loads(response.text)


async def _estimate_grounded(client, payload: FoodEstimateRequest) -> dict:
    """Two-turn tool-calling flow: Gemini's function calling and its
    structured JSON output mode (response_mime_type) cannot both be
    requested in the same call, so the first turn offers the USDA search
    tool with plain text output, and (whether or not Gemini actually used
    the tool - it decides for itself via AUTO mode) a second turn asks for
    the final structured JSON with the tool removed.
    """
    contents: list[types.Content] = [
        types.Content(
            role="user", parts=[types.Part.from_text(text=f"Estimate the nutrition for: {payload.description}")]
        )
    ]

    first = client.models.generate_content(
        model="gemini-flash-latest",
        contents=contents,
        config={
            "system_instruction": ESTIMATE_SYSTEM_PROMPT,
            "tools": [USDA_SEARCH_TOOL],
            "tool_config": {"function_calling_config": {"mode": "AUTO"}},
            "http_options": _HTTP_OPTIONS,
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
        model="gemini-flash-latest",
        contents=contents,
        config={
            "system_instruction": ESTIMATE_SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "http_options": _HTTP_OPTIONS,
        },
    )
    return json.loads(final.text)


@router.post("/estimate", response_model=FoodEstimateResponse)
@limiter.limit(estimate_rate_limit)
async def estimate_food(request: Request, payload: FoodEstimateRequest):
    """Send a free-text food description to Gemini and return a structured
    nutritional estimate. Does not touch the database — the frontend calls
    POST /foods with the result if the user accepts it.

    Rate-limited (5/min anonymous, 15/min authenticated) since this is the
    one endpoint that costs real Gemini quota per call and has no auth
    requirement of its own to naturally throttle abuse.
    """
    if not payload.description.strip():
        raise HTTPException(status_code=422, detail="Description cannot be empty")

    client = get_gemini_client()

    try:
        if _needs_grounding(payload.description):
            data = await _estimate_grounded(client, payload)
        else:
            data = await _estimate_simple(client, payload)
        estimate = NutritionalEstimate(
            name=data["name"],
            serving_size_value=Decimal(str(data["serving_size_value"])),
            serving_size_unit=data["serving_size_unit"],
            calories=int(data["calories"]),
            protein_g=Decimal(str(data["protein_g"])),
            carbs_g=Decimal(str(data["carbs_g"])),
            fat_g=Decimal(str(data["fat_g"])),
            confidence=float(data["confidence"]),
            notes=data.get("notes"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI estimation failed: {e}") from e

    return FoodEstimateResponse(description=payload.description, estimate=estimate)


@router.post("", response_model=UserCustomFoodResponse)
async def create_custom_food(
    payload: UserCustomFoodCreate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    result = (
        db.table("custom_foods")
        .insert({**payload.model_dump(mode="json"), "user_id": str(user.id)})
        .execute()
    )
    return result.data[0]


@router.get("", response_model=list[UserCustomFoodResponse])
async def list_my_foods(
    page: Pagination = Depends(pagination),
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    result = (
        db.table("custom_foods")
        .select("*")
        .eq("user_id", str(user.id))
        .range(*page.range())
        .execute()
    )
    return result.data
