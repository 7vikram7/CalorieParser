import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client

from app.core import llm
from app.core.auth import get_current_user, get_current_user_client
from app.core.pagination import Pagination, pagination
from app.core.rate_limit import estimate_rate_limit, limiter
from app.models.estimation import FoodEstimateRequest, FoodEstimateResponse, NutritionalEstimate
from app.models.food import UserCustomFoodCreate, UserCustomFoodResponse
from app.models.user import UserResponse

router = APIRouter(prefix="/foods", tags=["foods"])
logger = logging.getLogger(__name__)


def _needs_grounding(description: str) -> bool:
    """Whether this description is worth the USDA-tool-augmented Gemini
    flow, versus the cheap Groq path.

    This exists because of a discovery made while building tool use: the
    Gemini free tier's real binding constraint (revealed by a 429 response,
    not documented anywhere beforehand) is
    GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20 requests/day for
    gemini-3.7-flash (what gemini-flash-latest currently resolves to).
    Provider-agnostic (just looks at the description), so it stays here
    rather than in app/core/llm.py - it's a routing decision, not
    provider logic.
    """
    word_count = len(description.split())
    return word_count > 8 or "," in description or " and " in description.lower()


@router.post("/estimate", response_model=FoodEstimateResponse)
@limiter.limit(estimate_rate_limit)
async def estimate_food(request: Request, payload: FoodEstimateRequest):
    """Send a free-text food description to an LLM and return a structured
    nutritional estimate. Does not touch the database — the frontend calls
    POST /foods with the result if the user accepts it.

    Checks the estimate_cache table first (zero LLM calls on a repeat
    description), then routes to Groq (cheap, fast, no meaningful quota
    limit) or Gemini+USDA grounding (more accurate on multi-item meals,
    but capped at 20 requests/day on the free tier - see
    app/core/llm.py:_is_gemini_unavailable for the fallback this forces).

    Rate-limited (5/min anonymous, 15/min authenticated) since this is the
    one endpoint that costs real LLM quota per call and has no auth
    requirement of its own to naturally throttle abuse.
    """
    description = payload.description.strip()
    if not description:
        raise HTTPException(status_code=422, detail="Description cannot be empty")

    try:
        data = llm.get_cached_estimate(description)
        if data is None:
            if _needs_grounding(description):
                data = await llm.estimate_grounded(description)
                source = "gemini"
            else:
                data = await llm.estimate_simple(description)
                source = "groq"
            llm.set_cached_estimate(description, data, source=source)
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
