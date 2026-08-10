import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.core.gemini import get_gemini_client
from app.core.pagination import Pagination, pagination
from app.core.rate_limit import estimate_rate_limit, limiter
from app.models.estimation import FoodEstimateRequest, FoodEstimateResponse, NutritionalEstimate
from app.models.food import UserCustomFoodCreate, UserCustomFoodResponse
from app.models.user import UserResponse

router = APIRouter(prefix="/foods", tags=["foods"])

ESTIMATE_SYSTEM_PROMPT = """You are a professional nutritionist AI. Given a natural-language
meal description, estimate the nutritional content as accurately as possible.

Return a JSON object with exactly these fields:
- name: short descriptive name for the meal/food item
- serving_size_value: numeric amount (e.g. 1.0, 200.0)
- serving_size_unit: unit string (e.g. "serving", "ml", "g", "piece")
- calories: integer total kcal
- protein_g: grams of protein (decimal)
- carbs_g: grams of carbohydrates (decimal)
- fat_g: grams of fat (decimal)
- confidence: float 0.0-1.0 indicating how confident you are in this estimate
- notes: string with any caveats, assumptions, or clarifications (null if none)

Be realistic. If the description is vague, estimate conservatively and lower the
confidence score. If you cannot estimate at all, set confidence to 0.0 and explain
in notes."""


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

    try:
        response = get_gemini_client().models.generate_content(
            model="gemini-flash-latest",
            contents=f"Estimate the nutrition for: {payload.description}",
            config={
                "system_instruction": ESTIMATE_SYSTEM_PROMPT,
                "response_mime_type": "application/json",
            },
        )
        data = json.loads(response.text)
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
